"""Unit tests for RobotController."""

import logging
import threading
import time
from pathlib import Path
from unittest.mock import MagicMock

import numpy as np
import pytest
from websockets.exceptions import ConnectionClosedError
from websockets.frames import Close

from reachy_alive.control.commands import RobotCommand
from reachy_alive.control.robot_controller import RobotController
from reachy_alive.shared_state import SharedState


def run_one_tick(command, reachy_mini, shared_state=None) -> None:
    """Run RobotController's loop for exactly one tick, executing ``command``."""
    stop_event = threading.Event()

    def decide(*args, **kwargs):
        stop_event.set()  # the loop exits after this tick
        return command

    action_selector = MagicMock()
    action_selector.decide.side_effect = decide

    RobotController(action_selector, MagicMock()).run(
        reachy_mini, shared_state or SharedState(), stop_event
    )

def test_robot_command_sends_the_pose_to_the_robot(fake_reachy_mini):
    head = np.eye(4)
    antennas = np.array([-0.17, 0.17])

    run_one_tick(RobotCommand(head=head, antennas=antennas), fake_reachy_mini)

    fake_reachy_mini.set_target.assert_called_once()
    sent = fake_reachy_mini.set_target.call_args.kwargs
    assert sent["head"] is head
    assert sent["antennas"] is antennas


def test_a_failing_tick_still_puts_the_robot_to_sleep(fake_reachy_mini):
    action_selector = MagicMock()
    action_selector.decide.side_effect = RuntimeError("a move failed")

    with pytest.raises(RuntimeError):
        RobotController(action_selector, MagicMock()).run(
            fake_reachy_mini, SharedState(), threading.Event()
        )

    fake_reachy_mini.goto_sleep.assert_called_once()
    fake_reachy_mini.disable_motors.assert_called_once()


def test_a_lost_connection_stays_the_error_that_stops_the_app(fake_reachy_mini, caplog):
    lost = ConnectionError("Lost connection with the server.")
    fake_reachy_mini.set_target.side_effect = lost
    fake_reachy_mini.goto_sleep.side_effect = ConnectionError("Lost connection with the server.")
    action_selector = MagicMock()
    action_selector.decide.return_value = RobotCommand(head=np.eye(4), antennas=np.zeros(2))

    with caplog.at_level(logging.WARNING, logger="reachy_alive"):
        with pytest.raises(ConnectionError) as raised:
            RobotController(action_selector, MagicMock()).run(
                fake_reachy_mini, SharedState(), threading.Event()
            )

    assert raised.value is lost  # the tick's error, not the shutdown's
    assert "Could not put the robot to sleep" in caplog.text
    fake_reachy_mini.disable_motors.assert_not_called()


def test_a_websocket_closed_at_shutdown_is_a_lost_connection_too(fake_reachy_mini, caplog):
    # In the first second, before the SDK notices, writing to the closed
    # WebSocket raises from websockets, "from None": that hid the loop's error.
    restart = Close(1012, "service restart")
    lost = ConnectionClosedError(restart, restart, True)
    fake_reachy_mini.set_target.side_effect = lost
    fake_reachy_mini.goto_sleep.side_effect = ConnectionClosedError(restart, restart, True)
    action_selector = MagicMock()
    action_selector.decide.return_value = RobotCommand(head=np.eye(4), antennas=np.zeros(2))

    with caplog.at_level(logging.WARNING, logger="reachy_alive"):
        with pytest.raises(ConnectionClosedError) as raised:
            RobotController(action_selector, MagicMock()).run(
                fake_reachy_mini, SharedState(), threading.Event()
            )

    assert raised.value is lost
    assert "Could not put the robot to sleep" in caplog.text


def test_any_other_error_at_shutdown_still_shows(fake_reachy_mini):
    fake_reachy_mini.goto_sleep.side_effect = RuntimeError("a bug in going to sleep")
    stop_event = threading.Event()
    stop_event.set()

    with pytest.raises(RuntimeError, match="a bug in going to sleep"):
        RobotController(MagicMock(), MagicMock()).run(fake_reachy_mini, SharedState(), stop_event)


def test_waking_up_counts_as_a_move_playing(fake_reachy_mini):
    state = SharedState()
    playing_during_wake_up = []
    playing_once_awake = []
    fake_reachy_mini.wake_up.side_effect = lambda: playing_during_wake_up.append(
        state.is_move_playing()
    )
    fake_reachy_mini.set_target.side_effect = lambda **_: playing_once_awake.append(
        state.is_move_playing()
    )

    run_one_tick(RobotCommand(head=np.eye(4), antennas=np.zeros(2)), fake_reachy_mini, state)

    assert playing_during_wake_up == [True]
    assert playing_once_awake == [False]  # back to poses, before going to sleep


def test_robot_command_records_the_pose_it_sends(fake_reachy_mini):
    state = SharedState()
    head = np.eye(4)
    antennas = np.array([-0.17, 0.17])
    before = time.monotonic()

    run_one_tick(RobotCommand(head=head, antennas=antennas), fake_reachy_mini, state)

    pose = state.last_commanded_pose()
    assert pose.head is head
    assert pose.antennas is antennas
    assert pose.at >= before


def test_going_to_sleep_counts_as_a_move_playing(fake_reachy_mini):
    state = SharedState()
    playing_while_going_to_sleep = []
    fake_reachy_mini.goto_sleep.side_effect = lambda: playing_while_going_to_sleep.append(
    state.is_move_playing()
    )

    run_one_tick(RobotCommand(head=np.eye(4), antennas=np.zeros(2)), fake_reachy_mini, state)

    assert playing_while_going_to_sleep == [True]


class FakeClock:
    """Stands in for the time module: time moves only when told, or when slept."""

    def __init__(self, now: float) -> None:
        self.now = now
        self.slept_s: list[float] = []

    def monotonic(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.slept_s.append(seconds)
        self.now += seconds


@pytest.fixture
def clock(monkeypatch):
    """Freeze RobotController's clock at 0 s."""
    fake = FakeClock(now=0.0)
    monkeypatch.setattr("reachy_alive.control.robot_controller.time", fake)
    return fake


def test_an_early_tick_sleeps_until_the_next_one_is_due(clock):
    clock.now = 0.015

    due_at = RobotController(MagicMock(), MagicMock())._wait_for_next_tick(0.020)

    assert clock.slept_s == [pytest.approx(0.005)]
    assert due_at == 0.020


def test_a_tick_late_by_less_than_one_slot_is_followed_at_once(clock, caplog):
    clock.now = 0.030

    due_at = RobotController(MagicMock(), MagicMock())._wait_for_next_tick(0.020)

    assert clock.slept_s == []
    assert due_at == 0.020  # the next one is due at 40 ms
    assert caplog.records == []


def test_a_tick_late_by_a_whole_slot_skips_it_and_says_so(clock, caplog):
    clock.now = 0.045

    due_at = RobotController(MagicMock(), MagicMock())._wait_for_next_tick(0.020)

    assert clock.slept_s == []
    assert due_at == pytest.approx(0.040)  # 20 ms gone, the next one is due at 60 ms
    assert "Skipped 1 ticks (25 ms late)" in caplog.text


def test_a_long_stall_is_followed_by_one_tick_not_a_burst(clock, caplog):
    clock.now = 0.200

    due_at = RobotController(MagicMock(), MagicMock())._wait_for_next_tick(0.020)

    assert clock.slept_s == []
    assert due_at == pytest.approx(0.200)  # the next one is due at 220 ms
    assert "Skipped 9 ticks" in caplog.text


def test_robot_command_hands_its_sounds_to_the_sound_player(fake_reachy_mini):
    sneeze = Path("/local/sneeze.wav")
    sound_player = MagicMock()
    controller = RobotController(MagicMock(), sound_player)
    command = RobotCommand(head=np.eye(4), antennas=np.zeros(2), sounds=(sneeze,))

    controller._execute(command, fake_reachy_mini, SharedState())

    sound_player.play.assert_called_once_with(sneeze)
    fake_reachy_mini.media.play_sound.assert_not_called()  # never from the loop


def test_the_sound_player_runs_as_long_as_the_loop_and_stops_before_sleep(fake_reachy_mini):
    sound_player = MagicMock()
    fake_reachy_mini.attach_mock(sound_player, "sound_player")
    action_selector = MagicMock()
    action_selector.decide.side_effect = RuntimeError("a tick failed")

    with pytest.raises(RuntimeError):
        RobotController(action_selector, sound_player).run(
            fake_reachy_mini, SharedState(), threading.Event()
        )

    calls = [name for name, _, _ in fake_reachy_mini.mock_calls]
    assert calls.index("wake_up") < calls.index("sound_player.start")
    assert calls.index("sound_player.stop") < calls.index("goto_sleep")


def test_breathing_leaves_the_body_where_it_is(fake_reachy_mini):
    run_one_tick(RobotCommand(head=np.eye(4), antennas=np.zeros(2)), fake_reachy_mini)

    assert fake_reachy_mini.set_target.call_args.kwargs["body_yaw"] is None


def test_robot_command_records_the_body_yaw_it_sends(fake_reachy_mini):
    state = SharedState()

    run_one_tick(
        RobotCommand(head=np.eye(4), antennas=np.zeros(2), body_yaw=0.3), fake_reachy_mini, state
    )

    assert state.last_commanded_pose().body_yaw == 0.3


def test_a_pose_from_a_move_counts_as_a_move_playing(fake_reachy_mini):
    state = SharedState()
    controller = RobotController(MagicMock(), MagicMock())

    controller._execute(
        RobotCommand(head=np.eye(4), antennas=np.zeros(2), from_move=True), fake_reachy_mini, state
    )

    assert state.is_move_playing() is True


def test_the_first_pose_after_a_move_ends_it(fake_reachy_mini):
    state = SharedState()
    controller = RobotController(MagicMock(), MagicMock())
    from_move = RobotCommand(head=np.eye(4), antennas=np.zeros(2), from_move=True)
    breathing = RobotCommand(head=np.eye(4), antennas=np.zeros(2))

    controller._execute(from_move, fake_reachy_mini, state)
    assert state.last_move_ended_at() is None  # not while the move plays
    controller._execute(breathing, fake_reachy_mini, state)

    assert state.is_move_playing() is False
    assert state.last_move_ended_at() is not None


def test_breathing_alone_never_ends_a_move(fake_reachy_mini):
    state = SharedState()
    controller = RobotController(MagicMock(), MagicMock())

    for _ in range(3):
        controller._execute(
            RobotCommand(head=np.eye(4), antennas=np.zeros(2)), fake_reachy_mini, state
        )

    assert state.last_move_ended_at() is None

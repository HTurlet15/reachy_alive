"""Unit tests for RobotController."""

import threading
import time
from unittest.mock import MagicMock

import numpy as np
import pytest

from reachy_alive.control.commands import HoldPose, PlayMove
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

    RobotController(action_selector).run(
        reachy_mini, shared_state or SharedState(), stop_event
    )

def test_records_the_move_as_playing_only_while_it_plays(fake_reachy_mini):
    state = SharedState()
    playing_during_play = []
    move = MagicMock()
    move.play.side_effect = lambda _: playing_during_play.append(state.is_move_playing())

    RobotController(MagicMock())._execute(PlayMove(move), fake_reachy_mini, state)

    assert playing_during_play == [True]  # seen from inside the move
    assert state.is_move_playing() is False  # and over once it has ended


def test_move_stops_playing_even_when_the_move_fails(fake_reachy_mini):
    state = SharedState()
    move = MagicMock()
    move.play.side_effect = RuntimeError("the move failed")

    with pytest.raises(RuntimeError):
        RobotController(MagicMock())._execute(PlayMove(move), fake_reachy_mini, state)

    assert state.is_move_playing() is False

def test_restarts_idle_timer_once_the_move_has_ended(fake_reachy_mini):
    state = SharedState()
    state.last_activity_at = time.monotonic() - 50.0
    timer_during_play = []
    move = MagicMock()
    move.play.side_effect = lambda _: timer_during_play.append(
        state.seconds_since_last_activity()
    )

    run_one_tick(PlayMove(move), fake_reachy_mini, state)

    assert timer_during_play[0] >= 50.0  # not reset while the move runs
    assert state.seconds_since_last_activity() < 0.1  # reset once it has ended


def test_hold_pose_leaves_the_idle_timer_alone(fake_reachy_mini):
    state = SharedState()
    state.last_activity_at = time.monotonic() - 50.0

    run_one_tick(HoldPose(head=np.eye(4), antennas=np.zeros(2)), fake_reachy_mini, state)

    assert state.seconds_since_last_activity() >= 50.0

def test_hold_pose_sends_the_pose_to_the_robot(fake_reachy_mini):
    head = np.eye(4)
    antennas = np.array([-0.17, 0.17])

    run_one_tick(HoldPose(head=head, antennas=antennas), fake_reachy_mini)

    fake_reachy_mini.set_target.assert_called_once()
    sent = fake_reachy_mini.set_target.call_args.kwargs
    assert sent["head"] is head
    assert sent["antennas"] is antennas


def test_play_move_command_plays_the_move(fake_reachy_mini):
    move = MagicMock()

    run_one_tick(PlayMove(move), fake_reachy_mini)

    move.play.assert_called_once_with(fake_reachy_mini)
    fake_reachy_mini.set_target.assert_not_called()


def test_unknown_command_raises_and_still_puts_the_robot_to_sleep(fake_reachy_mini):
    with pytest.raises(TypeError):
        run_one_tick("not a command", fake_reachy_mini)

    fake_reachy_mini.goto_sleep.assert_called_once()
    fake_reachy_mini.disable_motors.assert_called_once()


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

    run_one_tick(HoldPose(head=np.eye(4), antennas=np.zeros(2)), fake_reachy_mini, state)

    assert playing_during_wake_up == [True]
    assert playing_once_awake == [False]  # back to poses, before going to sleep


def test_hold_pose_records_the_pose_it_sends(fake_reachy_mini):
    state = SharedState()
    head = np.eye(4)
    antennas = np.array([-0.17, 0.17])
    before = time.monotonic()

    run_one_tick(HoldPose(head=head, antennas=antennas), fake_reachy_mini, state)

    pose = state.last_commanded_pose()
    assert pose.head is head
    assert pose.antennas is antennas
    assert pose.at >= before


def test_play_move_records_no_pose(fake_reachy_mini):
    state = SharedState()

    run_one_tick(PlayMove(MagicMock()), fake_reachy_mini, state)

    assert state.last_commanded_pose() is None

def test_going_to_sleep_counts_as_a_move_playing(fake_reachy_mini):
    state = SharedState()
    playing_while_going_to_sleep = []
    fake_reachy_mini.goto_sleep.side_effect = lambda: playing_while_going_to_sleep.append(
    state.is_move_playing()
    )

    run_one_tick(HoldPose(head=np.eye(4), antennas=np.zeros(2)), fake_reachy_mini, state)

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

    due_at = RobotController(MagicMock())._wait_for_next_tick(0.020)

    assert clock.slept_s == [pytest.approx(0.005)]
    assert due_at == 0.020


def test_a_tick_late_by_less_than_one_slot_is_followed_at_once(clock, caplog):
    clock.now = 0.030

    due_at = RobotController(MagicMock())._wait_for_next_tick(0.020)

    assert clock.slept_s == []
    assert due_at == 0.020  # the next one is due at 40 ms
    assert caplog.records == []


def test_a_tick_late_by_a_whole_slot_skips_it_and_says_so(clock, caplog):
    clock.now = 0.045

    due_at = RobotController(MagicMock())._wait_for_next_tick(0.020)

    assert clock.slept_s == []
    assert due_at == pytest.approx(0.040)  # 20 ms gone, the next one is due at 60 ms
    assert "Skipped 1 ticks (25 ms late)" in caplog.text


def test_a_long_stall_is_followed_by_one_tick_not_a_burst(clock, caplog):
    clock.now = 0.200

    due_at = RobotController(MagicMock())._wait_for_next_tick(0.020)

    assert clock.slept_s == []
    assert due_at == pytest.approx(0.200)  # the next one is due at 220 ms
    assert "Skipped 9 ticks" in caplog.text


def test_a_move_holding_the_loop_is_not_a_late_tick(fake_reachy_mini, caplog):
    move = MagicMock()
    move.play.side_effect = lambda _: time.sleep(0.1)  # five ticks long

    run_one_tick(PlayMove(move), fake_reachy_mini)

    assert "Skipped" not in caplog.text

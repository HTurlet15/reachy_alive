"""Unit tests for ActionSelector, with still moves on a simulated clock."""

import queue
from pathlib import Path
from unittest.mock import MagicMock

import numpy as np
import pytest

from reachy_alive.brain.basal_ganglia.action_selector import ActionSelector
from reachy_alive.brain.brainstem.idle_manager import IdleManager
from reachy_alive.control.robot_controller import RobotController
from reachy_alive.moves.base import NEUTRAL_ANTENNAS_RAD, SoundCue
from reachy_alive.shared_state import SharedState
from tests.conftest import SoundsAtOnce, StillMove

SNEEZE = Path("/local/sneeze.wav")


def idle_proposing(move):
    """An IdleManager that proposes ``move`` (None: nothing) on every tick."""
    idle_manager = MagicMock()
    idle_manager.propose.return_value = move
    return idle_manager


class Loop:
    """Runs a selector tick by tick, sending each command to a fake robot."""

    def __init__(self, idle_manager, fake_reachy_mini, requests=None, state=None) -> None:
        self.state = state or SharedState()
        self.requests = requests or queue.Queue()
        self.selector = ActionSelector(idle_manager, self.requests, self.state)
        sounds = SoundsAtOnce(fake_reachy_mini, {SNEEZE: "/robot/sneeze.wav"})
        self.controller = RobotController(self.selector, sounds)
        self.fake_reachy_mini = fake_reachy_mini

    def tick(self, now):
        command = self.selector.decide(now)
        self.controller._execute(command, self.fake_reachy_mini, self.state)
        return command

    def ticks(self, start_s, end_s, step_s=0.02):
        """Run every tick from start_s up to end_s, and return their commands."""
        return [self.tick(now) for now in np.arange(start_s, end_s, step_s)]


def test_plays_the_idle_move_idle_proposes(fake_reachy_mini):
    loop = Loop(idle_proposing(StillMove()), fake_reachy_mini)

    command = loop.tick(1.0)

    assert command.from_move
    assert command.body_yaw == StillMove.BODY_YAW_RAD


def test_breathes_when_nobody_proposes_a_move(fake_reachy_mini):
    loop = Loop(idle_proposing(None), fake_reachy_mini)

    assert not loop.tick(1.0).from_move


def test_a_requested_move_wins_over_idle(fake_reachy_mini):
    idle_manager = idle_proposing(StillMove())
    requested = StillMove()
    requested.BODY_YAW_RAD = -0.4
    loop = Loop(idle_manager, fake_reachy_mini)
    loop.requests.put(requested)

    assert loop.tick(1.0).body_yaw == -0.4
    idle_manager.propose.assert_not_called()


def test_only_the_latest_request_plays(fake_reachy_mini):
    first, latest = StillMove(), StillMove()
    loop = Loop(idle_proposing(None), fake_reachy_mini)
    loop.requests.put(first)
    loop.requests.put(latest)

    loop.tick(1.0)

    assert (first.draws, latest.draws) == (0, 1)
    assert loop.requests.empty()


def test_a_sound_goes_out_once_on_the_first_tick_at_its_cue(fake_reachy_mini):
    move = StillMove(duration=0.2, sound_cues=[SoundCue(at_s=0.05, path=SNEEZE)])
    loop = Loop(idle_proposing(move), fake_reachy_mini)

    commands = loop.ticks(1.0, 1.2)  # ticks 0, 20, 40, 60 ms… into the move

    assert [command.sounds for command in commands[:4]] == [(), (), (), (SNEEZE,)]
    fake_reachy_mini.media.play_sound.assert_called_once_with("/robot/sneeze.wav")


def test_the_way_back_starts_from_the_last_pose_sent_and_ends_at_neutral(fake_reachy_mini):
    idle_manager = idle_proposing(StillMove(duration=0.1))
    loop = Loop(idle_manager, fake_reachy_mini)
    loop.tick(1.0)  # the move starts
    idle_manager.propose.return_value = None

    commands = loop.ticks(1.02, 1.8)
    from_move = [command for command in commands if command.from_move]

    way_back = from_move[4:]  # the move's ticks at 20 to 80 ms, then the way back
    np.testing.assert_allclose(way_back[0].antennas, StillMove.ANTENNAS)
    np.testing.assert_allclose(way_back[-1].antennas, NEUTRAL_ANTENNAS_RAD, atol=1e-3)


def test_nobody_is_heard_while_a_move_and_its_way_back_play(fake_reachy_mini):
    idle_manager = idle_proposing(StillMove(duration=0.1))
    loop = Loop(idle_manager, fake_reachy_mini)
    loop.tick(1.0)  # the idle move starts
    requested = StillMove()
    loop.requests.put(requested)

    commands = loop.ticks(1.02, 1.57)  # the rest of the move, then most of its way back

    assert all(command.from_move for command in commands)
    assert idle_manager.propose.call_count == 1
    assert requested.draws == 0
    loop.tick(1.62)  # the way back is over: the request plays on this very tick
    assert requested.draws == 1


def assert_neutral(command):
    """Check that a breathing command is the neutral pose, where breathing starts."""
    assert not command.from_move
    np.testing.assert_allclose(command.head, np.eye(4), atol=1e-9)
    np.testing.assert_allclose(command.antennas, NEUTRAL_ANTENNAS_RAD)


def test_breathing_starts_from_neutral(fake_reachy_mini):
    assert_neutral(Loop(idle_proposing(None), fake_reachy_mini).tick(7.3))


def test_breathing_keeps_its_own_rhythm_between_moves(fake_reachy_mini):
    loop = Loop(idle_proposing(None), fake_reachy_mini)
    loop.tick(5.0)

    command = loop.tick(6.0)  # 1 s into the breath

    assert not np.allclose(command.antennas, NEUTRAL_ANTENNAS_RAD)


def test_breathing_restarts_from_neutral_after_a_move(fake_reachy_mini):
    idle_manager = idle_proposing(None)
    loop = Loop(idle_manager, fake_reachy_mini)
    loop.ticks(5.0, 6.0)  # a second of breathing
    idle_manager.propose.return_value = StillMove(duration=0.1)
    loop.tick(6.0)  # an idle move starts
    idle_manager.propose.return_value = None

    commands = loop.ticks(6.02, 7.0)

    assert_neutral(next(command for command in commands if not command.from_move))


def test_the_end_of_a_move_restarts_the_idle_timer(fake_reachy_mini):
    idle_manager = idle_proposing(StillMove(duration=0.1))
    loop = Loop(idle_manager, fake_reachy_mini)
    loop.tick(1.0)
    idle_manager.propose.return_value = None

    loop.ticks(1.02, 2.0)

    assert loop.state.last_move_ended_at() is not None
    assert not loop.state.is_move_playing()


# time.monotonic() starts anywhere: the robot's timing must not depend on it.
@pytest.mark.parametrize("clock_at_start", [0.0, 18342.7])
def test_the_robot_rests_for_the_whole_delay_between_two_idle_moves(
    fake_reachy_mini, clock_at_start
):
    # The real IdleManager: with a mock, the idle moves once ran back to back.
    state = SharedState()
    state.set_idle_move_interval_range_s(5.0, 5.0)
    loop = Loop(IdleManager([StillMove(duration=2.0)], state), fake_reachy_mini, state=state)

    times = np.round(clock_at_start + np.arange(0.0, 20.0, 0.02), 2)
    commands = [loop.tick(now) for now in times]
    starts = [
        float(now - clock_at_start)
        for now, before, after in zip(times[1:], commands[:-1], commands[1:], strict=True)
        if after.from_move and not before.from_move
    ]

    # 2 s of move, 0.5 s of way back, then 5 s of rest again.
    assert starts == pytest.approx([5.0, 12.5])

# tests/test_robot_manager.py
"""Unit tests for RobotManager."""

import threading
from unittest.mock import MagicMock

import numpy as np
import pytest
import time

from reachy_alive.commands import HoldPose, PlayMove
from reachy_alive.robot_manager import RobotManager
from reachy_alive.shared_state import SharedState


def run_one_tick(command, reachy_mini, shared_state=None) -> None:
    """Run RobotManager's loop for exactly one tick, executing ``command``."""
    stop_event = threading.Event()

    def decide(*args, **kwargs):
        stop_event.set()  # the loop exits after this tick
        return command

    idle_manager = MagicMock()
    idle_manager.decide.side_effect = decide

    RobotManager(idle_manager).run(
        reachy_mini,
        shared_state or SharedState(),
        stop_event,
        get_antennas_enabled=lambda: True,
    )

def test_restarts_idle_timer_once_the_gesture_has_ended(fake_reachy_mini):
    state = SharedState()
    state.last_activity_at = time.monotonic() - 50.0
    timer_during_play = []
    move = MagicMock()
    move.play.side_effect = lambda _: timer_during_play.append(
        state.seconds_since_last_activity()
    )

    run_one_tick(PlayMove(move), fake_reachy_mini, state)

    assert timer_during_play[0] >= 50.0  # not reset while the gesture runs
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


def test_play_move_plays_the_gesture(fake_reachy_mini):
    move = MagicMock()

    run_one_tick(PlayMove(move), fake_reachy_mini)

    move.play.assert_called_once_with(fake_reachy_mini)
    fake_reachy_mini.set_target.assert_not_called()


def test_unknown_command_raises_and_still_puts_the_robot_to_sleep(fake_reachy_mini):
    with pytest.raises(TypeError):
        run_one_tick("not a command", fake_reachy_mini)

    fake_reachy_mini.goto_sleep.assert_called_once()
    fake_reachy_mini.disable_motors.assert_called_once()
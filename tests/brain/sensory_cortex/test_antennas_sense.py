"""Unit tests for AntennasSense, with a fake robot and poses recorded by hand."""

import math
from unittest.mock import MagicMock

import numpy as np

from reachy_alive.brain.sensory_cortex.antennas import AntennasSense
from reachy_alive.shared_state import CommandedPose, SharedState

NEUTRAL_RAD = np.array([-0.17, 0.17])  # [right, left]


def make_sense() -> tuple[AntennasSense, SharedState, MagicMock]:
    """Build a sense on a fake robot that hasn't moved itself.

    RobotController has sent the antennas to NEUTRAL_RAD, and the fake robot
    measures them there until a test moves them.
    """
    reachy_mini = MagicMock()
    reachy_mini.get_present_antenna_joint_positions.return_value = list(NEUTRAL_RAD)
    state = SharedState()
    state.record_commanded_pose(CommandedPose(at=0.0, head=np.eye(4), antennas=NEUTRAL_RAD))
    return AntennasSense(reachy_mini, state), state, reachy_mini


def read_for(sense: AntennasSense, start_s: float, duration_s: float) -> float:
    """Read every 10 ms from start_s for duration_s; return the time after."""
    t = start_s
    while t < start_s + duration_s:
        sense.read_once(t)
        t += 0.01
    return t


def test_antennas_where_they_were_sent_are_not_pushed():
    sense, state, _ = make_sense()

    read_for(sense, 0.0, 1.0)

    assert state.antenna_pushed_since("right") is None
    assert state.antenna_pushed_since("left") is None


def test_records_a_push_on_the_antenna_moved_away():
    sense, state, reachy_mini = make_sense()
    t = read_for(sense, 0.0, 0.5)
    reachy_mini.get_present_antenna_joint_positions.return_value = [
        NEUTRAL_RAD[0],
        NEUTRAL_RAD[1] + math.radians(10.0),
    ]

    sense.read_once(t)

    assert state.antenna_pushed_since("left") == t
    assert state.antenna_pushed_since("right") is None


def test_a_released_antenna_is_no_longer_pushed():
    sense, state, reachy_mini = make_sense()
    t = read_for(sense, 0.0, 0.5)
    reachy_mini.get_present_antenna_joint_positions.return_value = [
        NEUTRAL_RAD[0] + math.radians(10.0),
        NEUTRAL_RAD[1],
    ]
    t = read_for(sense, t, 0.2)
    reachy_mini.get_present_antenna_joint_positions.return_value = list(NEUTRAL_RAD)

    sense.read_once(t)

    assert state.antenna_pushed_since("right") is None


def test_stays_quiet_while_a_move_plays():
    sense, state, reachy_mini = make_sense()
    t = read_for(sense, 0.0, 0.5)
    state.set_move_playing(True)
    reachy_mini.get_present_antenna_joint_positions.return_value = [
        NEUTRAL_RAD[0] + math.radians(30.0),
        NEUTRAL_RAD[1] + math.radians(30.0),
    ]

    read_for(sense, t, 0.5)

    assert state.antenna_pushed_since("right") is None
    assert state.antenna_pushed_since("left") is None


def test_stays_quiet_until_a_pose_was_sent():
    reachy_mini = MagicMock()
    reachy_mini.get_present_antenna_joint_positions.return_value = [1.0, 1.0]
    state = SharedState()  # RobotController hasn't sent any pose yet
    sense = AntennasSense(reachy_mini, state)

    read_for(sense, 0.0, 0.5)

    assert state.antenna_pushed_since("right") is None
    assert state.antenna_pushed_since("left") is None


def test_stays_quiet_right_after_the_robot_moved_itself():
    sense, state, reachy_mini = make_sense()
    state.set_move_playing(True)
    sense.read_once(0.0)
    state.set_move_playing(False)
    reachy_mini.get_present_antenna_joint_positions.return_value = [
        NEUTRAL_RAD[0] + math.radians(30.0),
        NEUTRAL_RAD[1] + math.radians(30.0),
    ]

    read_for(sense, 0.01, 0.3)  # within settle_after_move_s

    assert state.antenna_pushed_since("right") is None
    assert state.antenna_pushed_since("left") is None
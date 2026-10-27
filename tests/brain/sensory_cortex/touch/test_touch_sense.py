"""Unit tests for TouchSense, with a fake robot and poses recorded by hand."""

from unittest.mock import MagicMock

import numpy as np

from reachy_alive.brain.sensory_cortex.touch.touch_sense import TouchSense
from reachy_alive.shared_state import CommandedPose, SharedState

SENT_RAD = np.array([-0.17, 0.17])  # [right, left]
MEASURED_RAD = [-0.15, 0.20]


def make_sense(pose_sent: bool = True) -> tuple[TouchSense, SharedState]:
    """Build a sense on a fake robot that measures MEASURED_RAD."""
    reachy_mini = MagicMock()
    reachy_mini.get_present_antenna_joint_positions.return_value = MEASURED_RAD
    state = SharedState()
    if pose_sent:
        state.record_commanded_pose(CommandedPose(at=0.0, head=np.eye(4), antennas=SENT_RAD))
    return TouchSense(reachy_mini, state), state


def test_the_features_hold_where_the_antennas_were_sent_and_where_they_are():
    sense, _ = make_sense()

    features = sense.read_once(12.0)

    assert features.perceived_at == 12.0
    assert features.targets_rad == (-0.17, 0.17)
    assert features.measured_rad == (-0.15, 0.20)
    assert features.robot_moving_itself is False


def test_no_features_until_a_pose_was_sent():
    sense, _ = make_sense(pose_sent=False)

    assert sense.read_once(0.0) is None


def test_the_features_say_when_a_move_plays():
    sense, state = make_sense()
    state.set_move_playing(True)

    assert sense.read_once(0.0).robot_moving_itself is True


def test_the_features_say_when_the_robot_just_moved_itself():
    sense, state = make_sense()
    state.set_move_playing(True)
    state.set_move_playing(False)
    ended_at = state.last_move_ended_at()

    assert sense.read_once(ended_at + 0.3).robot_moving_itself is True  # within SETTLE_AFTER_MOVE_S
    assert sense.read_once(ended_at + 1.0).robot_moving_itself is False


def test_both_antennas_are_felt_at_first():
    sense, _ = make_sense()

    assert sense.read_once(0.0).antennas_enabled == (True, True)


def test_an_antenna_switched_off_from_the_page_is_not_felt():
    sense, state = make_sense()
    state.set_sense_enabled("touch.right", False)

    assert sense.read_once(0.0).antennas_enabled == (False, True)

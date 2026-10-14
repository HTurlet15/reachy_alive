"""Unit tests for InertialSense, with a fake robot whose inertial unit always reads the same."""

import logging
from unittest.mock import MagicMock

from reachy_alive.brain.sensory_cortex.inertial.inertial_sense import InertialSense
from reachy_alive.shared_state import SharedState

JOLT = {"accelerometer": [0.0, 0.0, 15.0]}


def make_sense(imu: dict | None) -> tuple[InertialSense, SharedState]:
    """Build a sense on a fake robot that never moved."""
    reachy_mini = MagicMock()
    reachy_mini.imu = imu
    state = SharedState()
    return InertialSense(reachy_mini, state), state


def test_the_features_hold_the_reading_and_its_time():
    sense, _ = make_sense(JOLT)

    features = sense.read_once(12.0)

    assert features.t == 12.0
    assert features.accelerometer == (0.0, 0.0, 15.0)
    assert features.robot_moving_itself is False


def test_the_features_say_when_a_move_plays():
    sense, state = make_sense(JOLT)
    state.set_move_playing(True)

    assert sense.read_once(0.0).robot_moving_itself is True


def test_the_features_say_when_a_move_just_ended():
    sense, state = make_sense(JOLT)
    state.set_move_playing(True)
    state.set_move_playing(False)

    assert sense.read_once(state.last_move_ended_at() + 0.1).robot_moving_itself is True


def test_without_data_there_are_no_features_and_it_says_so_once(caplog):
    sense, _ = make_sense(None)

    with caplog.at_level(logging.INFO):
        first, second = sense.read_once(1.0), sense.read_once(2.0)

    assert first is None and second is None
    assert caplog.text.count("No inertial unit data") == 1
# tests/brainstem/test_idle_manager.py
"""Unit tests for IdleManager."""

from unittest.mock import MagicMock

import numpy as np

from reachy_alive.brainstem.idle_manager import IdleManager
from reachy_alive.moves.base import NEUTRAL_ANTENNAS_RAD
from reachy_alive.shared_state import SharedState


def test_returns_breathing_pose_when_not_time_for_a_gesture(fake_reachy_mini):
    state = SharedState()
    state.mark_activity()
    manager = IdleManager([MagicMock()], gesture_interval_range_s=(100.0, 100.0))

    pose = manager.get_pose(t=1.0, shared_state=state, reachy_mini=fake_reachy_mini)

    assert pose is not None


def test_triggers_a_gesture_and_resets_activity(fake_reachy_mini):
    state = SharedState()
    behavior = MagicMock()
    manager = IdleManager([behavior], gesture_interval_range_s=(0.0, 0.0))

    pose = manager.get_pose(t=1.0, shared_state=state, reachy_mini=fake_reachy_mini)

    assert pose is None
    behavior.play.assert_called_once_with(fake_reachy_mini)
    assert state.seconds_since_last_activity() < 0.1


def test_breathing_restarts_from_neutral_after_a_gesture(fake_reachy_mini):
    state = SharedState()
    manager = IdleManager([MagicMock()], gesture_interval_range_s=(0.0, 0.0))
    manager.get_pose(t=5.0, shared_state=state, reachy_mini=fake_reachy_mini)  # plays
    manager.gesture_interval_range_s = (100.0, 100.0)  # no gesture next tick

    head, antennas = manager.get_pose(t=12.3, shared_state=state, reachy_mini=fake_reachy_mini)

    np.testing.assert_allclose(head, np.eye(4), atol=1e-9)
    np.testing.assert_allclose(antennas, NEUTRAL_ANTENNAS_RAD)
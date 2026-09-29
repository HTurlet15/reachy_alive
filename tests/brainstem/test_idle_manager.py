# tests/brainstem/test_idle_manager.py
"""Unit tests for IdleManager."""

import logging
import time
from unittest.mock import MagicMock

import numpy as np

from reachy_alive.brainstem.idle_manager import IdleManager
from reachy_alive.commands import HoldPose, PlayMove
from reachy_alive.moves.base import NEUTRAL_ANTENNAS_RAD
from reachy_alive.shared_state import SharedState


def test_returns_breathing_pose_when_not_time_for_a_gesture(fake_reachy_mini):
    state = SharedState()
    state.mark_activity()
    manager = IdleManager([MagicMock()], gesture_interval_range_s=(100.0, 100.0))

    command = manager.decide(t=1.0, shared_state=state, reachy_mini=fake_reachy_mini)

    assert isinstance(command, HoldPose)


def test_hands_off_a_gesture_without_playing_it(fake_reachy_mini):
    behavior = MagicMock()
    manager = IdleManager([behavior], gesture_interval_range_s=(0.0, 0.0))

    command = manager.decide(t=1.0, shared_state=SharedState(), reachy_mini=fake_reachy_mini)

    assert isinstance(command, PlayMove)
    assert command.move is behavior
    behavior.play.assert_not_called()


def test_never_touches_the_idle_timer(fake_reachy_mini):
    state = SharedState()
    # Age the idle timer instead of sleeping: nothing happened for 50 s.
    state.last_activity_at = time.monotonic() - 50.0
    manager = IdleManager([MagicMock()], gesture_interval_range_s=(0.0, 0.0))

    manager.decide(t=1.0, shared_state=state, reachy_mini=fake_reachy_mini)  # hands off
    manager.gesture_interval_range_s = (100.0, 100.0)
    manager.decide(t=9.0, shared_state=state, reachy_mini=fake_reachy_mini)  # breathes

    assert state.seconds_since_last_activity() >= 50.0


def test_breathing_restarts_from_neutral_after_a_gesture(fake_reachy_mini):
    state = SharedState()
    manager = IdleManager([MagicMock()], gesture_interval_range_s=(0.0, 0.0))
    manager.decide(t=5.0, shared_state=state, reachy_mini=fake_reachy_mini)  # hands off
    manager.gesture_interval_range_s = (100.0, 100.0)  # no gesture next tick

    command = manager.decide(t=12.3, shared_state=state, reachy_mini=fake_reachy_mini)

    assert isinstance(command, HoldPose)
    np.testing.assert_allclose(command.head, np.eye(4), atol=1e-9)
    np.testing.assert_allclose(command.antennas, NEUTRAL_ANTENNAS_RAD)


def test_logs_which_gesture_plays(fake_reachy_mini, caplog):
    behavior = MagicMock()
    behavior.name = "sneezing"
    manager = IdleManager([behavior], gesture_interval_range_s=(0.0, 0.0))

    with caplog.at_level(logging.INFO, logger="reachy_alive"):
        manager.decide(t=1.0, shared_state=SharedState(), reachy_mini=fake_reachy_mini)

    assert "Playing sneezing" in caplog.text


def test_breathing_restarts_from_neutral_after_an_interrupt(fake_reachy_mini):
    state = SharedState()
    state.mark_activity()
    manager = IdleManager([MagicMock()], gesture_interval_range_s=(100.0, 100.0))
    manager.decide(t=5.0, shared_state=state, reachy_mini=fake_reachy_mini)  # breathing starts

    manager.interrupt()
    command = manager.decide(t=12.3, shared_state=state, reachy_mini=fake_reachy_mini)

    np.testing.assert_allclose(command.head, np.eye(4), atol=1e-9)
    np.testing.assert_allclose(command.antennas, NEUTRAL_ANTENNAS_RAD)
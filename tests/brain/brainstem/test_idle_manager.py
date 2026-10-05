"""Unit tests for IdleManager."""

import logging
import time
from unittest.mock import MagicMock

import numpy as np

from reachy_alive.brain.brainstem.idle_manager import IdleManager
from reachy_alive.control.commands import HoldPose, PlayMove
from reachy_alive.moves.base import NEUTRAL_ANTENNAS_RAD
from reachy_alive.shared_state import SharedState


def state_with_interval(min_s: float, max_s: float) -> SharedState:
    """A fresh SharedState whose idle move interval is set to (min_s, max_s)."""
    state = SharedState()
    state.set_idle_move_interval_range_s(min_s, max_s)
    return state


def test_returns_breathing_pose_when_no_idle_move_is_due(fake_reachy_mini):
    state = state_with_interval(100.0, 100.0)
    manager = IdleManager([MagicMock()])

    command = manager.decide(t=1.0, shared_state=state, reachy_mini=fake_reachy_mini)

    assert isinstance(command, HoldPose)


def test_hands_off_an_idle_move_without_playing_it(fake_reachy_mini):
    idle_move = MagicMock()
    manager = IdleManager([idle_move])

    command = manager.decide(
        t=1.0, shared_state=state_with_interval(0.0, 0.0), reachy_mini=fake_reachy_mini
    )

    assert isinstance(command, PlayMove)
    assert command.move is idle_move
    idle_move.play.assert_not_called()


def test_draws_the_delay_from_the_shared_interval(fake_reachy_mini):
    state = state_with_interval(40.0, 40.0)
    manager = IdleManager([MagicMock()])

    state.last_activity_at = time.monotonic() - 39.0
    assert isinstance(
        manager.decide(t=1.0, shared_state=state, reachy_mini=fake_reachy_mini), HoldPose
    )

    state.last_activity_at = time.monotonic() - 41.0
    assert isinstance(
        manager.decide(t=2.0, shared_state=state, reachy_mini=fake_reachy_mini), PlayMove
    )


def test_a_new_interval_applies_from_the_next_idle_move(fake_reachy_mini):
    state = state_with_interval(10.0, 10.0)
    manager = IdleManager([MagicMock()])
    manager.decide(t=1.0, shared_state=state, reachy_mini=fake_reachy_mini)  # 10 s drawn

    state.set_idle_move_interval_range_s(100.0, 100.0)
    state.last_activity_at = time.monotonic() - 11.0
    command = manager.decide(t=2.0, shared_state=state, reachy_mini=fake_reachy_mini)

    assert isinstance(command, PlayMove)  # the 10 s already drawn still applies
    

def test_never_touches_the_idle_timer(fake_reachy_mini):
    state = state_with_interval(0.0, 0.0)
    # Age the idle timer instead of sleeping: nothing happened for 50 s.
    state.last_activity_at = time.monotonic() - 50.0
    manager = IdleManager([MagicMock()])

    manager.decide(t=1.0, shared_state=state, reachy_mini=fake_reachy_mini)  # hands off
    state.set_idle_move_interval_range_s(100.0, 100.0)
    manager.decide(t=9.0, shared_state=state, reachy_mini=fake_reachy_mini)  # breathes

    assert state.seconds_since_last_activity() >= 50.0


def test_breathing_restarts_from_neutral_after_an_idle_move(fake_reachy_mini):
    state = state_with_interval(0.0, 0.0)
    manager = IdleManager([MagicMock()])
    manager.decide(t=5.0, shared_state=state, reachy_mini=fake_reachy_mini)  # hands off
    state.set_idle_move_interval_range_s(100.0, 100.0)  # no idle move next tick

    command = manager.decide(t=12.3, shared_state=state, reachy_mini=fake_reachy_mini)

    assert isinstance(command, HoldPose)
    np.testing.assert_allclose(command.head, np.eye(4), atol=1e-9)
    np.testing.assert_allclose(command.antennas, NEUTRAL_ANTENNAS_RAD)


def test_logs_which_idle_move_plays(fake_reachy_mini, caplog):
    idle_move = MagicMock()
    idle_move.name = "sneezing"
    manager = IdleManager([idle_move])

    with caplog.at_level(logging.INFO, logger="reachy_alive"):
        manager.decide(
            t=1.0, shared_state=state_with_interval(0.0, 0.0), reachy_mini=fake_reachy_mini
        )

    assert "Playing sneezing" in caplog.text


def test_breathing_restarts_from_neutral_after_an_interrupt(fake_reachy_mini):
    state = state_with_interval(100.0, 100.0)
    manager = IdleManager([MagicMock()])
    manager.decide(t=5.0, shared_state=state, reachy_mini=fake_reachy_mini)  # breathing starts

    manager.interrupt()
    command = manager.decide(t=12.3, shared_state=state, reachy_mini=fake_reachy_mini)

    np.testing.assert_allclose(command.head, np.eye(4), atol=1e-9)
    np.testing.assert_allclose(command.antennas, NEUTRAL_ANTENNAS_RAD)
"""Unit tests for IdleManager."""

import logging
import time
from unittest.mock import MagicMock

from reachy_alive.brain.brainstem.idle_manager import IdleManager
from reachy_alive.shared_state import SharedState


def state_with_interval(min_s: float, max_s: float) -> SharedState:
    """A fresh SharedState whose idle move interval is set to (min_s, max_s)."""
    state = SharedState()
    state.set_idle_move_interval_range_s(min_s, max_s)
    return state


def test_proposes_nothing_while_no_idle_move_is_due():
    manager = IdleManager([MagicMock()], state_with_interval(100.0, 100.0))

    assert manager.propose() is None


def test_hands_off_an_idle_move_without_playing_it():
    idle_move = MagicMock()
    manager = IdleManager([idle_move], state_with_interval(0.0, 0.0))

    proposed = manager.propose()

    assert proposed is idle_move
    idle_move.play.assert_not_called()


def test_draws_the_delay_from_the_shared_interval():
    state = state_with_interval(40.0, 40.0)
    manager = IdleManager([MagicMock()], state)

    state.last_activity_at = time.monotonic() - 39.0
    assert manager.propose() is None

    state.last_activity_at = time.monotonic() - 41.0
    assert manager.propose() is not None


def test_a_new_interval_applies_from_the_next_idle_move():
    state = state_with_interval(10.0, 10.0)
    manager = IdleManager([MagicMock()], state)
    manager.propose()  # 10 s drawn

    state.set_idle_move_interval_range_s(100.0, 100.0)
    state.last_activity_at = time.monotonic() - 11.0

    assert manager.propose() is not None  # the 10 s already drawn still applies


def test_never_touches_the_idle_timer():
    state = state_with_interval(0.0, 0.0)
    # Age the idle timer instead of sleeping: nothing happened for 50 s.
    state.last_activity_at = time.monotonic() - 50.0
    manager = IdleManager([MagicMock()], state)

    manager.propose()  # hands off
    state.set_idle_move_interval_range_s(100.0, 100.0)
    manager.propose()  # proposes nothing

    assert state.seconds_since_last_activity() >= 50.0


def test_logs_which_idle_move_plays(caplog):
    idle_move = MagicMock()
    idle_move.name = "sneezing"
    manager = IdleManager([idle_move], state_with_interval(0.0, 0.0))

    with caplog.at_level(logging.INFO, logger="reachy_alive"):
        manager.propose()

    assert "Playing sneezing" in caplog.text

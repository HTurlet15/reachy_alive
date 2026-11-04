"""Unit tests for IdleManager."""

import logging
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

    assert manager.propose(resting_for_s=0.0) is None


def test_proposes_one_of_its_idle_moves_once_due():
    idle_move = MagicMock()
    manager = IdleManager([idle_move], state_with_interval(0.0, 0.0))

    assert manager.propose(resting_for_s=0.0) is idle_move


def test_draws_the_delay_from_the_shared_interval():
    manager = IdleManager([MagicMock()], state_with_interval(40.0, 40.0))

    assert manager.propose(resting_for_s=39.0) is None
    assert manager.propose(resting_for_s=41.0) is not None


def test_a_new_interval_applies_from_the_next_idle_move():
    state = state_with_interval(10.0, 10.0)
    manager = IdleManager([MagicMock()], state)
    manager.propose(resting_for_s=0.0)  # 10 s drawn

    state.set_idle_move_interval_range_s(100.0, 100.0)

    assert manager.propose(resting_for_s=11.0) is not None  # the 10 s drawn still applies
    assert manager.propose(resting_for_s=11.0) is None  # 100 s from now on


def test_logs_which_idle_move_plays(caplog):
    idle_move = MagicMock()
    idle_move.name = "sneezing"
    manager = IdleManager([idle_move], state_with_interval(0.0, 0.0))

    with caplog.at_level(logging.INFO, logger="reachy_alive"):
        manager.propose(resting_for_s=0.0)

    assert "Playing sneezing" in caplog.text

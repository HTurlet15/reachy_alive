# tests/test_shared_state.py
"""Unit tests for SharedState."""

import pytest
import time

from reachy_alive.shared_state import DEFAULT_IDLE_MOVE_INTERVAL_RANGE_S, SharedState


def test_seconds_since_last_activity_starts_near_zero():
    state = SharedState()
    assert state.seconds_since_last_activity() < 0.1


def test_mark_activity_resets_the_timer():
    state = SharedState()
    state.last_activity_at = time.monotonic() - 50.0

    state.mark_activity()

    assert state.seconds_since_last_activity() < 0.1


def test_seconds_since_last_activity_increases_over_time():
    state = SharedState()
    state.last_activity_at = time.monotonic() - 5.0
    assert state.seconds_since_last_activity() >= 5.0

def test_idle_move_interval_starts_at_the_default():
    assert SharedState().idle_move_interval_range_s() == DEFAULT_IDLE_MOVE_INTERVAL_RANGE_S


def test_set_idle_move_interval_replaces_the_pair():
    state = SharedState()
    state.set_idle_move_interval_range_s(60.0, 90.0)
    assert state.idle_move_interval_range_s() == (60.0, 90.0)


def test_set_idle_move_interval_rejects_min_above_max():
    state = SharedState()
    with pytest.raises(ValueError):
        state.set_idle_move_interval_range_s(90.0, 60.0)
    assert state.idle_move_interval_range_s() == DEFAULT_IDLE_MOVE_INTERVAL_RANGE_S
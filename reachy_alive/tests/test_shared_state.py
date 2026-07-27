# reachy_alive/tests/test_shared_state.py
"""Unit tests for SharedState."""

import time

from reachy_alive.shared_state import SharedState


def test_seconds_since_last_activity_is_zero_before_any_activity():
    state = SharedState()
    assert state.seconds_since_last_activity() == 0.0


def test_mark_activity_resets_the_timer():
    state = SharedState()
    state.mark_activity()
    assert state.seconds_since_last_activity() < 0.1


def test_seconds_since_last_activity_increases_over_time():
    state = SharedState()
    state.last_activity_at = time.time() - 5.0
    assert state.seconds_since_last_activity() >= 5.0
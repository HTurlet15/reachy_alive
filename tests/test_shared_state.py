# reachy_alive/tests/test_shared_state.py
"""Unit tests for SharedState."""

import time

from reachy_alive.shared_state import SharedState


def test_seconds_since_last_activity_starts_near_zero():
    state = SharedState()
    assert state.seconds_since_last_activity() < 0.1


def test_mark_activity_resets_the_timer():
    state = SharedState()
    state.mark_activity()
    assert state.seconds_since_last_activity() < 0.1


def test_seconds_since_last_activity_increases_over_time():
    state = SharedState()
    state.last_activity_at = time.monotonic() - 5.0
    assert state.seconds_since_last_activity() >= 5.0
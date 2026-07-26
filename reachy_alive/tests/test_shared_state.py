# reachy_alive/tests/test_shared_state.py
"""Unit tests for SharedState."""

import time

from reachy_alive.shared_state import SharedState


def test_is_external_active_false_when_no_command_yet():
    state = SharedState()
    assert state.is_external_active() is False


def test_is_external_active_true_within_cooldown():
    state = SharedState()
    state.last_external_command_at = time.time()
    assert state.is_external_active(cooldown_s=2.0) is True


def test_is_external_active_false_after_cooldown_expires():
    state = SharedState()
    state.last_external_command_at = time.time() - 5.0  # 5s ago
    assert state.is_external_active(cooldown_s=2.0) is False
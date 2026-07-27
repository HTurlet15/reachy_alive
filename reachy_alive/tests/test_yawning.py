# reachy_alive/tests/test_yawning.py
"""Unit tests for Yawning."""

from reachy_alive.brainstem.custom_idle_moves.yawning import Yawning


def test_trigger_plays_rise_hold_and_release(fake_reachy_mini):
    Yawning().trigger(fake_reachy_mini)

    assert fake_reachy_mini.goto_target.call_count == 3  # rise, hold, release
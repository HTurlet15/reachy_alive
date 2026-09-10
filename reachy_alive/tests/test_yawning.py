# reachy_alive/tests/test_yawning.py
"""Unit tests for Yawning."""

from reachy_alive.moves.yawning import Yawning


def test_trigger_plays_the_rise_loop_then_returns_to_neutral(fake_reachy_mini):
    Yawning().trigger(fake_reachy_mini)

    assert fake_reachy_mini.set_target.called  # rise + hold loop
    assert fake_reachy_mini.goto_target.call_count == 1  # release
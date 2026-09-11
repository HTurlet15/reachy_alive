# reachy_alive/tests/test_yawning.py
"""Unit tests for Yawning."""

from reachy_alive.moves.yawning import Yawning


def test_trigger_plays_rise_hold_return_and_shake_then_settles(fake_reachy_mini):
    Yawning().trigger(fake_reachy_mini)

    assert fake_reachy_mini.set_target.called  # rise + hold + return + shake loop
    assert fake_reachy_mini.goto_target.call_count == 1  # final settle
    assert fake_reachy_mini.media.play_sound.call_count == 2  # inhale + yawn
# reachy_alive/tests/test_stretching.py
"""Unit tests for Stretching.

NOTE: this test runs the real trigger() logic, including the ~0.6s
tremble loop (time.sleep isn't mocked) -- it's slow (~1s) but simple;
mock time.sleep later if the test suite's runtime becomes a problem.
"""

from reachy_alive.brainstem.custom_idle_moves.stretching import Stretching


def test_trigger_plays_wind_up_reach_and_release(fake_reachy_mini):
    Stretching().trigger(fake_reachy_mini)

    assert fake_reachy_mini.goto_target.call_count == 3  # wind up, reach, release
    assert fake_reachy_mini.set_target.called  # tremble phase
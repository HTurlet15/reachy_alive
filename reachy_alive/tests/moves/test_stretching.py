"""Unit tests for Stretching.

NOTE: runs the real motion loop without mocking time.sleep -- slow (~3s)
but simple.
"""

from reachy_alive.moves.stretching import Stretching


def test_play_runs_the_motion_loop_then_settles(fake_reachy_mini):
    Stretching().play(fake_reachy_mini)

    assert fake_reachy_mini.set_target.called  # crouch + rise + tremble loop
    assert fake_reachy_mini.goto_target.call_count == 2  # choreographed return + play()'s
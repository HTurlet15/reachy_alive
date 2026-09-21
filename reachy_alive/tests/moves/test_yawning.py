# reachy_alive/tests/moves/test_yawning.py
"""Unit tests for Yawning.

Runs the real motion loop without mocking time.sleep, so the test lasts as
long as the gesture itself.
"""

from reachy_alive.moves.yawning import Yawning


def test_play_uploads_sounds_streams_poses_and_returns_to_neutral(fake_reachy_mini):
    Yawning().play(fake_reachy_mini)

    assert fake_reachy_mini.media.audio.upload_sound.call_count == 3
    assert fake_reachy_mini.media.play_sound.call_count == 3  # inhale, exhale, shake
    assert fake_reachy_mini.set_target.called
    fake_reachy_mini.goto_target.assert_called_once()  # play()'s return to neutral
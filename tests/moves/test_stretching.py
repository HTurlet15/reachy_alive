"""Unit tests for Stretching.

The play test goes through the ActionSelector, the MovePlayer and the
controller, on a simulated clock.
"""

from reachy_alive.moves.stretching import Stretching


def test_play_uploads_sounds_streams_poses_and_returns_to_neutral(play, fake_reachy_mini):
    play(Stretching())

    assert fake_reachy_mini.media.audio.upload_sound.call_count == 3
    assert fake_reachy_mini.media.play_sound.call_count == 3  # rising, stretching, release
    assert fake_reachy_mini.set_target.called
    fake_reachy_mini.goto_target.assert_not_called()  # the return is streamed too

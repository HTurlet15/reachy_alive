# reachy_alive/tests/test_library_move.py
"""Unit tests for LibraryMove."""

from unittest.mock import MagicMock, patch

from reachy_alive.library_move import LibraryMove


@patch("reachy_alive.library_move._EMOTIONS")
def test_trigger_plays_the_named_move_with_sound(mock_emotions, fake_reachy_mini):
    mock_move = MagicMock()
    mock_emotions.get.return_value = mock_move

    LibraryMove("boredom1").trigger(fake_reachy_mini)

    mock_emotions.get.assert_called_once_with("boredom1")
    fake_reachy_mini.play_move.assert_called_once_with(mock_move, sound=True)
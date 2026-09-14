# reachy_alive/tests/test_library_move.py
"""Unit tests for LibraryMove."""

from unittest.mock import MagicMock

from reachy_alive.moves.base import LibraryMove


def test_play_plays_the_named_move_with_sound(fake_reachy_mini):
    library = MagicMock()
    move = library.get.return_value

    LibraryMove("boredom1", library).play(fake_reachy_mini)

    library.get.assert_called_once_with("boredom1")
    fake_reachy_mini.play_move.assert_called_once_with(move, sound=True)
# reachy_alive/tests/test_move.py
"""Unit tests for the return to neutral Move.play() adds around a move."""

from unittest.mock import MagicMock

from reachy_alive.moves.base import NEUTRAL_ANTENNAS_RAD, LibraryMove


def test_play_returns_to_neutral_after_the_move(fake_reachy_mini):
    LibraryMove("boredom1", MagicMock()).play(fake_reachy_mini)

    fake_reachy_mini.goto_target.assert_called_once()
    assert fake_reachy_mini.goto_target.call_args.kwargs["antennas"] == NEUTRAL_ANTENNAS_RAD


def test_play_performs_the_move_before_returning_to_neutral(fake_reachy_mini):
    library = MagicMock()

    LibraryMove("boredom1", library).play(fake_reachy_mini)

    library.get.assert_called_once_with("boredom1")
    fake_reachy_mini.play_move.assert_called_once()
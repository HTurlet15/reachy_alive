"""Move interface and library-backed implementation."""

from abc import ABC, abstractmethod

from reachy_mini import ReachyMini
from reachy_mini.motion.recorded_move import RecordedMoves


class Move(ABC):
    """A discrete, one-off action the robot can play."""

    @abstractmethod
    def trigger(self, reachy_mini: ReachyMini) -> None:
        """Play this move on the robot.

        Args:
            reachy_mini: Connected robot instance.
        """


class LibraryMove(Move):
    """Plays a named move from a recorded-moves library."""

    def __init__(self, move_name: str, library: RecordedMoves) -> None:
        self.move_name = move_name
        self._library = library

    def trigger(self, reachy_mini: ReachyMini) -> None:
        reachy_mini.play_move(self._library.get(self.move_name), sound=True)
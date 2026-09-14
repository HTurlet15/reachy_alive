"""Move interface and library-backed implementation."""

from abc import ABC, abstractmethod

from reachy_mini import ReachyMini
from reachy_mini.utils import create_head_pose
from reachy_mini.motion.recorded_move import RecordedMoves

# The SDK's own neutral is offset ~10° off vertical, not [0.0, 0.0] --
# straight up is where antennas jitter (upstream hardware limit).
NEUTRAL_ANTENNAS_RAD = [-0.1745, 0.1745]


class Move(ABC):
    """A discrete, one-off action the robot can play.

    Subclasses implement `_perform`; callers use `play`, which always
    leaves the robot at neutral so the next behavior starts from a known
    pose.
    """

    RETURN_DURATION_S = 0.5

    def play(self, reachy_mini: ReachyMini) -> None:
        """Play this move, then return the robot to neutral.

        Args:
            reachy_mini: Connected robot instance.
        """
        self._perform(reachy_mini)
        self.go_neutral(reachy_mini)

    @abstractmethod
    def _perform(self, reachy_mini: ReachyMini) -> None:
        """Play the move itself, free to end on any pose.

        Args:
            reachy_mini: Connected robot instance.
        """

    def go_neutral(self, reachy_mini: ReachyMini, duration: float | None = None) -> None:
        """Move the robot to the neutral head and antenna pose.

        Args:
            reachy_mini: Connected robot instance.
            duration: Movement duration in seconds. Defaults to RETURN_DURATION_S.
        """
        reachy_mini.goto_target(
            head=create_head_pose(),
            antennas=NEUTRAL_ANTENNAS_RAD,
            duration=duration or self.RETURN_DURATION_S,
        )


class LibraryMove(Move):
    """Plays a named move from a recorded-moves library."""

    def __init__(self, move_name: str, library: RecordedMoves) -> None:
        self.move_name = move_name
        self._library = library

    def _perform(self, reachy_mini: ReachyMini) -> None:
        reachy_mini.play_move(self._library.get(self.move_name), sound=True)

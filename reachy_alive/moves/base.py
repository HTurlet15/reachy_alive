"""Move interface and library-backed implementation."""

from abc import ABC, abstractmethod

from reachy_mini import ReachyMini
from reachy_mini.utils import create_head_pose
from reachy_mini.motion.recorded_move import RecordedMoves

# The SDK's own neutral is offset ~10° off vertical, not [0.0, 0.0] --
# straight up is where antennas jitter (upstream hardware limit).
NEUTRAL_ANTENNAS_RAD = [-0.1745, 0.1745]


class Move(ABC):
    """A discrete, one-off action the robot can play."""

    RETURN_DURATION_S = 0.5

    @abstractmethod
    def trigger(self, reachy_mini: ReachyMini) -> None:
        """Play this move on the robot.

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

    def trigger(self, reachy_mini: ReachyMini) -> None:
        reachy_mini.play_move(self._library.get(self.move_name), sound=True)
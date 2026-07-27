from reachy_mini import ReachyMini
from reachy_mini.motion.recorded_move import RecordedMoves

from reachy_alive.custom_move import BaseMove

_EMOTIONS = RecordedMoves("pollen-robotics/reachy-mini-emotions-library")


class LibraryMove(BaseMove):
    """Plays a move directly from the emotions library, by name.

    This lets idle_manager treat library moves and fully custom gestures
    (like LookingAround) identically -- both expose trigger(reachy_mini).
    """

    def __init__(self, move_name: str) -> None:
        self.move_name = move_name

    def trigger(self, reachy_mini: ReachyMini) -> None:
        move = _EMOTIONS.get(self.move_name)
        reachy_mini.play_move(move, sound=True)
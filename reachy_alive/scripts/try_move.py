"""Manually trigger a single move on the robot, or in simulation, for visual testing.

Unit tests can verify that a move calls the SDK correctly, but not
that it looks right (correct tilt direction, amplitude, timing). This
script plays one move through the app's own control loop, exactly as the
app plays it, without idle moves around it.

Usage:
    uv run try-move stretching
    uv run try-move sneezing
    uv run try-move recorded hiccup-full
    uv run try-move pollen boredom1
"""

import argparse
import queue
import threading

from reachy_mini import ReachyMini
from reachy_mini.motion.recorded_move import RecordedMoves

from reachy_alive.brain.basal_ganglia.action_selector import ActionSelector
from reachy_alive.control.commands import RobotCommand
from reachy_alive.control.robot_controller import RobotController
from reachy_alive.control.sound_player import SoundPlayer
from reachy_alive.moves.base import LibraryMove
from reachy_alive.moves.robot_sounds import upload_sounds
from reachy_alive.moves.sneezing import Sneezing
from reachy_alive.moves.stretching import Stretching
from reachy_alive.moves.yawning import Yawning
from reachy_alive.shared_state import SharedState

# Moves written in code. Add yours here.
_CODED_MOVES = {
    "stretching": Stretching,
    "yawning": Yawning,
}

# Moves with a recorded head and coded antennas. They read the head from
# the "recorded" library. Add yours here.
_MIXED_MOVES = {
    "sneezing": Sneezing,
}

# Recorded-move libraries, by the subcommand that plays from them.
_LIBRARIES = {
    "pollen": "pollen-robotics/reachy-mini-emotions-library",
    "recorded": "HTurlet15/reachy-alive",
}

class _NoIdleMoves:
    """Stands in for IdleManager: proposes nothing, so only the requested move plays."""

    def propose(self, resting_for_s: float) -> None:
        return None


class _StopAfterTheMove:
    """Wraps the ActionSelector: stops the loop once the move and its way back are over."""

    def __init__(self, selector: ActionSelector, stop_event: threading.Event) -> None:
        self._selector = selector
        self._stop_event = stop_event
        self._move_seen = False

    def decide(self, now: float) -> RobotCommand:
        command = self._selector.decide(now)
        if command.from_move:
            self._move_seen = True
        elif self._move_seen:
            self._stop_event.set()
        return command


def main() -> None:
    """Parse CLI arguments, connect to the robot, and play the chosen move."""
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    for name in [*_CODED_MOVES, *_MIXED_MOVES]:
        subparsers.add_parser(name)

    for source, dataset in _LIBRARIES.items():
        source_parser = subparsers.add_parser(source)
        source_parser.add_argument("move_name", help=f"Name of the move in {dataset}")

    args = parser.parse_args()

    if args.command in _LIBRARIES:
        library = RecordedMoves(_LIBRARIES[args.command], token=False)
        move = LibraryMove(args.move_name, library)
    elif args.command in _MIXED_MOVES:
        library = RecordedMoves(_LIBRARIES["recorded"], token=False)
        move = _MIXED_MOVES[args.command](library)
    else:
        move = _CODED_MOVES[args.command]()

    # The control loop wakes the robot up first, and puts it back to sleep
    # once the move and its way back to neutral are over.
    with ReachyMini() as mini:
        shared_state = SharedState()
        requests: queue.Queue = queue.Queue()
        requests.put(move)
        stop_event = threading.Event()
        selector = ActionSelector(_NoIdleMoves(), requests, shared_state)
        controller = RobotController(
            _StopAfterTheMove(selector, stop_event),
            SoundPlayer(mini, upload_sounds([move], mini)),
        )
        controller.run(mini, shared_state, stop_event)


if __name__ == "__main__":
    main()

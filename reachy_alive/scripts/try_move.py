# reachy_alive/scripts/try_move.py
"""Manually trigger a single move on the real robot for visual testing.

Unit tests can verify that a gesture calls the SDK correctly, but not
that it looks right on hardware (correct tilt direction, amplitude,
timing). This script triggers one move directly, without going through
IdleManager or the full control loop.

Usage:
    python reachy_alive/scripts/try_move.py stretching
    python reachy_alive/scripts/try_move.py yawning
    python reachy_alive/scripts/try_move.py library boredom1
"""

import argparse

from reachy_mini import ReachyMini
from reachy_mini.motion.recorded_move import RecordedMoves

from reachy_alive.moves.base import LibraryMove
from reachy_alive.moves.stretching import Stretching
from reachy_alive.moves.yawning import Yawning

# Maps a CLI command name to its Move class.
# Add new hand-made gestures here as they're implemented.
_MOVES = {
    "stretching": Stretching,
    "yawning": Yawning,
}


def main() -> None:
    """Parse CLI arguments, connect to the robot, and trigger the chosen move."""
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    for name in _MOVES:
        subparsers.add_parser(name)

    library_parser = subparsers.add_parser("library")
    library_parser.add_argument(
        "move_name", help="Name of the move in the emotions library, e.g. boredom1"
    )

    args = parser.parse_args()

    if args.command == "library":
        emotions = RecordedMoves("pollen-robotics/reachy-mini-emotions-library")
        move = LibraryMove(args.move_name, emotions)
    else:
        move = _MOVES[args.command]()

    with ReachyMini() as mini:
        move.play(mini)


if __name__ == "__main__":
    main()
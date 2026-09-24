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
from reachy_alive.moves.sneezing import Sneezing
from reachy_alive.moves.stretching import Stretching
from reachy_alive.moves.yawning import Yawning

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
        library = RecordedMoves(_LIBRARIES[args.command])
        move = LibraryMove(args.move_name, library)
    elif args.command in _MIXED_MOVES:
        library = RecordedMoves(_LIBRARIES["recorded"])
        move = _MIXED_MOVES[args.command](library)
    else:
        move = _CODED_MOVES[args.command]()
        
    with ReachyMini() as mini:
        mini.enable_motors()
        try:
            move.go_neutral(mini, duration=2.0)
            move.play(mini)
        finally:
            mini.goto_sleep()
            mini.disable_motors()


if __name__ == "__main__":
    main()
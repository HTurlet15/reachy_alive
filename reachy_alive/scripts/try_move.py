# reachy_alive/scripts/try_move.py
"""Manually trigger a single move on the real robot, for visual testing."""

import argparse

from reachy_mini import ReachyMini

from reachy_alive.brainstem.custom_idle_moves.stretching import Stretching
from reachy_alive.brainstem.custom_idle_moves.yawning import Yawning
from reachy_alive.library_move import LibraryMove

_MOVES = {
    "stretching": Stretching,
    "yawning": Yawning,
}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("stretching")
    subparsers.add_parser("yawning")

    library_parser = subparsers.add_parser("library")
    library_parser.add_argument("move_name")

    args = parser.parse_args()

    if args.command == "library":
        move = LibraryMove(args.move_name)
    else:
        move = _MOVES[args.command]()

    with ReachyMini() as mini:
        move.trigger(mini)


if __name__ == "__main__":
    main()
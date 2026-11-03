"""Checks every shipped move against the move contract and the robot's limits.

Samples each move through evaluate() without running the motion loop, so
it's fast. Add your move to MOVES.

Recorded heads, like Sneezing's Marionette recording, are faked here: their
height isn't checked. Check them on the robot with `try-move`.
"""

import importlib
import pkgutil

import numpy as np
import pytest

import reachy_alive.moves as moves_package
from reachy_alive.moves.base import Move, PhasedMove
from reachy_alive.moves.sneezing import Sneezing
from reachy_alive.moves.stretching import Stretching
from reachy_alive.moves.yawning import Yawning

# Every PhasedMove, and how to build it from a recorded-moves library.
MOVES = {
    Yawning: lambda library: Yawning(),
    Stretching: lambda library: Stretching(),
    Sneezing: lambda library: Sneezing(library),
}

# Below this, the robot's inverse kinematics solver wedges for good
# (pollen-robotics/reachy_mini#1417).
LOWEST_HEAD_Z_M = -0.170


def _sampled_poses(move, samples_per_second=50):
    """Yield (t, pose) across the whole move, from its start to its end."""
    for t in np.linspace(0.0, move.duration, int(move.duration * samples_per_second) + 1):
        yield t, move.evaluate(t)


def _shipped_subclasses(base):
    """Return every subclass of base defined in the moves package, at any depth."""
    for module in pkgutil.iter_modules(moves_package.__path__):
        importlib.import_module(f"{moves_package.__name__}.{module.name}")

    found = set()
    to_visit = list(base.__subclasses__())
    while to_visit:
        cls = to_visit.pop()
        if cls.__module__.startswith(moves_package.__name__):
            found.add(cls)
        to_visit.extend(cls.__subclasses__())
    return found


def test_every_phased_move_is_in_moves():
    shipped = _shipped_subclasses(PhasedMove)

    missing = sorted(cls.__name__ for cls in shipped - MOVES.keys())

    assert not missing, f"{', '.join(missing)} not in MOVES, at the top of {__file__}"


def test_no_move_writes_its_own_execution_loop():
    # _perform is Move's internal loop, due to change. Defining it means
    # overriding it: every move only says its poses, through evaluate.
    moves = _shipped_subclasses(Move)

    offenders = sorted(cls.__name__ for cls in moves if "_perform" in vars(cls))

    assert not offenders, (
        f"{', '.join(offenders)} define _perform. Subclass PhasedMove or use "
        "LibraryMove, and draw per-play values in start."
    )


@pytest.mark.parametrize("move_class", MOVES, ids=lambda cls: cls.__name__)
def test_every_pose_follows_the_contract(move_class, fake_library):
    move = MOVES[move_class](fake_library)

    for t, (head, antennas, body_yaw) in _sampled_poses(move):
        assert np.shape(head) == (4, 4), t
        assert len(antennas) == 2, t
        assert np.isscalar(body_yaw), t


@pytest.mark.parametrize("move_class", MOVES, ids=lambda cls: cls.__name__)
def test_head_never_goes_below_the_reachable_workspace(move_class, fake_library):
    move = MOVES[move_class](fake_library)

    for t, (head, _, _) in _sampled_poses(move):
        assert head[2, 3] >= LOWEST_HEAD_Z_M, t


def test_no_two_moves_share_a_sound_file_name(fake_library):
    # Uploads to the robot are keyed by file name: two sounds with the same
    # name overwrite each other's copy.
    paths = {path for build in MOVES.values() for path in build(fake_library).sound_paths()}
    names = [path.name for path in paths]

    shared = sorted({name for name in names if names.count(name) > 1})

    assert not shared, f"Sound file names used by several moves: {', '.join(shared)}"

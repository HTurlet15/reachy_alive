# tests/moves/test_pose_contract.py
"""Checks every PhasedMove against the pose contract and the robot's limits.

Samples each phase without running the motion loop, so it's fast. Add your
move to MOVES.
"""

import importlib
import pkgutil

import numpy as np
import pytest

import reachy_alive.moves as moves_package
from reachy_alive.moves.base import PhasedMove
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


def _sampled_poses(move, samples_per_phase=25):
    """Yield (phase, pose) across the whole gesture, phase by phase."""
    phase_start_s = 0.0
    step = 0
    for phase, phase_end_s in move.phase_ends_s.items():
        for p in np.linspace(0.0, 1.0, samples_per_phase):
            elapsed_s = phase_start_s + p * (phase_end_s - phase_start_s)
            yield phase, move._pose_at(phase, p, step, elapsed_s)
            step += 1
        phase_start_s = phase_end_s


def test_every_phased_move_is_in_moves():
    for module in pkgutil.iter_modules(moves_package.__path__):
        importlib.import_module(f"{moves_package.__name__}.{module.name}")
    shipped = {
        cls
        for cls in PhasedMove.__subclasses__()
        if cls.__module__.startswith(moves_package.__name__)
    }

    missing = sorted(cls.__name__ for cls in shipped - MOVES.keys())

    assert not missing, f"{', '.join(missing)} not in MOVES, at the top of {__file__}"


@pytest.mark.parametrize("move_class", MOVES, ids=lambda cls: cls.__name__)
def test_every_pose_follows_the_contract(move_class, fake_library):
    move = MOVES[move_class](fake_library)

    for phase, (head, antennas, body_yaw) in _sampled_poses(move):
        assert np.shape(head) == (4, 4), phase
        assert len(antennas) == 2, phase
        assert np.isscalar(body_yaw), phase


@pytest.mark.parametrize("move_class", MOVES, ids=lambda cls: cls.__name__)
def test_head_never_goes_below_the_reachable_workspace(move_class, fake_library):
    move = MOVES[move_class](fake_library)

    for phase, (head, _, _) in _sampled_poses(move):
        assert head[2, 3] >= LOWEST_HEAD_Z_M, phase
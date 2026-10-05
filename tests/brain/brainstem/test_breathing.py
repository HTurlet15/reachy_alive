"""Unit tests for the breathing pose."""

import numpy as np

from reachy_alive.brain.brainstem.breathing import get_breathing_pose
from reachy_alive.moves.base import NEUTRAL_ANTENNAS_RAD


def test_breathing_starts_where_every_move_ends():
    # play() ends every move at neutral; breathing must pick up from there.
    head, antennas = get_breathing_pose(0.0)

    np.testing.assert_allclose(head, np.eye(4), atol=1e-9)
    np.testing.assert_allclose(antennas, NEUTRAL_ANTENNAS_RAD)


def test_antennas_sway_around_neutral_not_vertical():
    _, antennas = get_breathing_pose(1.0)  # a quarter period in: full sway

    sway = np.deg2rad(15.0)
    np.testing.assert_allclose(antennas, [NEUTRAL_ANTENNAS_RAD[0] + sway, NEUTRAL_ANTENNAS_RAD[1] - sway])
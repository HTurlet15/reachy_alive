"""Continuous breathing: the pose the robot holds between moves."""

import numpy as np
from reachy_mini.utils import create_head_pose

from reachy_alive.moves.base import NEUTRAL_ANTENNAS_RAD

# The head rises and falls; the antennas sway around neutral.
HEAD_AMPLITUDE_MM = 4.0
HEAD_FREQUENCY_HZ = 0.25
ANTENNA_AMPLITUDE_DEG = 15.0
ANTENNA_FREQUENCY_HZ = 0.25


def get_breathing_pose(t: float) -> tuple[np.ndarray, np.ndarray]:
    """Return the head and antenna pose for continuous breathing.

    At t = 0 this is the neutral pose, where every move ends, so
    breathing can restart from 0 after a move without a jump.

    Args:
        t: Seconds since breathing started.

    Returns:
        (head pose, antennas in ANTENNA_SIDES order (right, left), in
        radians).
    """
    z = HEAD_AMPLITUDE_MM * np.sin(2 * np.pi * HEAD_FREQUENCY_HZ * t)
    head_pose = create_head_pose(z=z, mm=True)

    sway_rad = np.deg2rad(ANTENNA_AMPLITUDE_DEG) * np.sin(2 * np.pi * ANTENNA_FREQUENCY_HZ * t)
    antennas_rad = np.array(NEUTRAL_ANTENNAS_RAD) + np.array([sway_rad, -sway_rad])

    return head_pose, antennas_rad

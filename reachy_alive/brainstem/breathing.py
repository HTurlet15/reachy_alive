# reachy_alive/brainstem/breathing.py
"""Continuous breathing: the pose the robot holds between gestures."""

import numpy as np
from reachy_mini.utils import create_head_pose

from reachy_alive.moves.base import NEUTRAL_ANTENNAS_RAD


def get_breathing_pose(
    t: float,
    amplitude_mm: float = 4.0,
    frequency_hz: float = 0.25,
    antenna_amplitude_deg: float = 15.0,
    antenna_frequency_hz: float = 0.25,
) -> tuple[np.ndarray, np.ndarray]:
    """Return the head and antenna pose for continuous breathing.

    At t = 0 this is the neutral pose, where every gesture ends, so
    breathing can restart from 0 after a gesture without a jump.

    Args:
        t: Seconds since breathing started.
        amplitude_mm: Vertical head motion, in millimeters.
        frequency_hz: Breathing rate.
        antenna_amplitude_deg: Antenna sway around neutral, in degrees.
        antenna_frequency_hz: Antenna sway rate.

    Returns:
        (head pose, [left antenna, right antenna] in radians).
    """
    z = amplitude_mm * np.sin(2 * np.pi * frequency_hz * t)
    head_pose = create_head_pose(z=z, mm=True)

    sway_rad = np.deg2rad(antenna_amplitude_deg) * np.sin(2 * np.pi * antenna_frequency_hz * t)
    antennas_rad = np.array(NEUTRAL_ANTENNAS_RAD) + np.array([sway_rad, -sway_rad])

    return head_pose, antennas_rad
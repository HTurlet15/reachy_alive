import numpy as np
from reachy_mini.utils import create_head_pose


def get_breathing_pose(t: float, amplitude_mm: float = 4.0, frequency_hz: float = 0.5):
    """
    Calculates the head pose for continuous breathing.

    Args:
        t: elapsed time in seconds (the same t as in the main.py run() loop)
        amplitude_mm: amplitude of the vertical movement, in mm
        frequency_hz: breathing rate (0.5 Hz = one cycle every 2 seconds)

    Returns:
        A head pose that can be used directly in reachy_mini.set_target(head=...)
    """

    z = amplitude_mm * np.sin(2 * np.pi * frequency_hz * t)

    return create_head_pose(z=z, mm=True)
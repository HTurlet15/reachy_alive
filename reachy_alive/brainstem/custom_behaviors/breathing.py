import numpy as np
from reachy_mini.utils import create_head_pose


def get_breathing_pose( t: float, antennas_enabled: bool = True, amplitude_mm: float = 4.0, frequency_hz: float = 0.5,
    antenna_amplitude_deg: float = 15.0, antenna_frequency_hz: float = 0.5, ):
    """
    Calculates head + antenna pose for continuous breathing.

    Args:
        t: elapsed time in seconds
        antennas_enabled: if False, antennas stay neutral (still breathe with the head)
        amplitude_mm / frequency_hz: head vertical motion
        antenna_amplitude_deg / antenna_frequency_hz: antenna sway

    Returns:
        (head_pose, antennas_rad) - ready for reachy_mini.set_target(head=..., antennas=...)
    """
    z = amplitude_mm * np.sin(2 * np.pi * frequency_hz * t)
    head_pose = create_head_pose(z=z, mm=True)

    if antennas_enabled:
        a = antenna_amplitude_deg * np.sin(2 * np.pi * antenna_frequency_hz * t)
        antennas_deg = np.array([a, -a])
    else:
        antennas_deg = np.zeros(2)

    antennas_rad = np.deg2rad(antennas_deg)
    return head_pose, antennas_rad
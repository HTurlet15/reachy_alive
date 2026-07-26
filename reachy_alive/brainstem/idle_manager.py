# reachy_alive/brainstem/idle_manager.py
"""Idle-behavior arbitration for the Brainstem."""

from typing import Optional, Tuple

import numpy as np

from brainstem.custom_behaviors.breathing import get_breathing_pose
from reachy_alive.shared_state import SharedState


class IdleManager:
    """Decides which idle behavior, if any, the Brainstem should run this tick.

    Returns a pose for the default idle behavior (breathing) unless an
    external command has priority, in which case it returns None so the
    caller skips sending a command this tick.

    Shared state is passed explicitly to each call rather than stored on
    the instance, keeping this class decoupled from state ownership and
    easy to unit test in isolation.
    """

    def __init__(self, external_cooldown_s: float = 2.0) -> None:
        """
        Args:
            external_cooldown_s: How long, in seconds, an external command
                suppresses idle behaviors after it occurs.
        """
        self.external_cooldown_s = external_cooldown_s

    def get_pose(
        self,
        t: float,
        shared_state: SharedState,
        antennas_enabled: bool = True,
    ) -> Optional[Tuple[np.ndarray, np.ndarray]]:
        """Compute the idle pose for the current tick, if any.

        Args:
            t: Elapsed time in seconds since the control loop started.
            shared_state: Shared state to check for recent external activity.
            antennas_enabled: Whether antennas should move.

        Returns:
            (head_pose, antennas_rad) if an idle behavior should run this
            tick, or None if an external command has priority.
        """
        if shared_state.is_external_active(self.external_cooldown_s):
            return None

        # TODO: choose among discrete gestures (yawning, stretching,
        # looking_around) once an internal timer fires. Breathing is the
        # only behavior implemented so far.
        return get_breathing_pose(t, antennas_enabled=antennas_enabled)
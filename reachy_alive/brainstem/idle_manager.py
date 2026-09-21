# reachy_alive/brainstem/idle_manager.py
"""Idle-behavior arbitration for the Brainstem."""

import random
from typing import List, Optional, Tuple

import numpy as np
from reachy_mini import ReachyMini

from reachy_alive.moves.base import Move
from reachy_alive.brainstem.breathing import get_breathing_pose
from reachy_alive.shared_state import SharedState


class IdleManager:
    """Picks between continuous breathing and occasional discrete gestures.

    Gestures fire at random intervals; breathing runs the rest of the time.
    The idle timer lives in SharedState so other decision-makers can reset it.
    """

    def __init__(
        self,
        behaviors: List[Move],
        gesture_interval_range_s: Tuple[float, float] = (30, 45.0),
    ) -> None:
        """
        Args:
            behaviors: Discrete gestures to pick from when the idle timer fires.
            gesture_interval_range_s: (min, max) seconds between gestures.
        """
        self.gesture_interval_range_s = gesture_interval_range_s
        self._behaviors = behaviors
        self._next_interval_s = self._roll_next_interval()

    def get_pose(
        self,
        t: float,
        shared_state: SharedState,
        reachy_mini: ReachyMini,
        antennas_enabled: bool = True,
    ) -> Optional[Tuple[np.ndarray, np.ndarray]]:
        """Return this tick's breathing pose, or trigger a gesture instead.

        Args:
            t: Elapsed time in seconds since the control loop started.
            shared_state: Read and reset the idle timer.
            reachy_mini: Robot instance, needed to play gestures.
            antennas_enabled: Whether antennas move during breathing.

        Returns:
            (head_pose, antennas_rad), or None if a gesture was triggered.
        """
        if shared_state.seconds_since_last_activity() >= self._next_interval_s:
            random.choice(self._behaviors).play(reachy_mini)
            shared_state.mark_activity()
            self._next_interval_s = self._roll_next_interval()
            return None

        return get_breathing_pose(t, antennas_enabled=antennas_enabled)

    def _roll_next_interval(self) -> float:
        """Pick a new random delay before the next gesture."""
        return random.uniform(*self.gesture_interval_range_s)
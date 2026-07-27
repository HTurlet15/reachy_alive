# reachy_alive/brainstem/idle_manager.py
"""Idle-behavior arbitration for the Brainstem."""

import random
from typing import List, Optional, Tuple

import numpy as np
from reachy_mini import ReachyMini

from reachy_alive.move import BaseMove
from reachy_alive.library_move import LibraryMove
from reachy_alive.brainstem.custom_idle_moves.breathing import get_breathing_pose
from reachy_alive.brainstem.custom_idle_moves.yawning import Yawning
from reachy_alive.shared_state import SharedState

# Checked via emotions.list_moves() on 2026-07-26. Closest available
# stand-ins for an idle, slightly-bored robot (no exact match exists).
_IDLE_LIBRARY_MOVES = ["boredom1", "boredom2", "waiting", "tired1"]


class IdleManager:
    """Decides which idle behavior, if any, the Brainstem should run this tick.

    Two layers:
    - Breathing (continuous, default): a pose computed every tick.
    - Discrete gestures (library moves or custom behaviors): triggered
      once, at random intervals, when the idle timer fires.

    The idle timer lives in SharedState (seconds_since_last_activity),
    not here -- so a future external reaction (Amygdala/Prefrontal) can
    reset it too, without IdleManager needing to know about them.

    Attributes:
        gesture_interval_range_s: (min, max) seconds between gestures.
    """

    def __init__(
        self, gesture_interval_range_s: Tuple[float, float] = (15.0, 40.0)
    ) -> None:
        self.gesture_interval_range_s = gesture_interval_range_s
        self._behaviors: List[BaseMove] = [LibraryMove(name) for name in _IDLE_LIBRARY_MOVES]
        self._next_interval_s = self._roll_next_interval()

    def get_pose(
        self,
        t: float,
        shared_state: SharedState,
        reachy_mini: ReachyMini,
        antennas_enabled: bool = True,
    ) -> Optional[Tuple[np.ndarray, np.ndarray]]:
        """Decide and, if needed, execute this tick's idle behavior.

        Args:
            t: Elapsed time in seconds since the control loop started.
            shared_state: Shared state to read/reset the idle timer.
            reachy_mini: Connected robot instance, needed to play gestures.
            antennas_enabled: Whether antennas should move during breathing.

        Returns:
            (head_pose, antennas_rad) if breathing is this tick's behavior.
            None if a gesture was just triggered (already sent to the robot).
        """
        if shared_state.seconds_since_last_activity() >= self._next_interval_s:
            behavior = random.choice(self._behaviors)
            behavior.trigger(reachy_mini)
            shared_state.mark_activity()
            self._next_interval_s = self._roll_next_interval()
            return None

        return get_breathing_pose(t, antennas_enabled=antennas_enabled)

    def _roll_next_interval(self) -> float:
        """Pick a new random delay before the next gesture."""
        return random.uniform(*self.gesture_interval_range_s)
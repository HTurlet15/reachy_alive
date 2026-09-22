# reachy_alive/brainstem/idle_manager.py
"""Idle-behavior arbitration for the Brainstem."""

import random
import threading
from typing import List, Optional, Tuple

import numpy as np
from reachy_mini import ReachyMini

from reachy_alive.brainstem.breathing import get_breathing_pose
from reachy_alive.moves.base import Move
from reachy_alive.shared_state import SharedState


class IdleManager:
    """Picks between continuous breathing and occasional discrete gestures.

    Gestures fire at random intervals; breathing runs the rest of the time.
    The next gesture is chosen in advance, so its sounds upload in the
    background while the robot is still breathing. The idle timer lives in
    SharedState so other decision-makers can reset it.
    """

    def __init__(
        self,
        behaviors: List[Move],
        gesture_interval_range_s: Tuple[float, float] = (30.0, 45.0),
    ) -> None:
        """Set up the gesture pool.

        Args:
            behaviors: Discrete gestures to pick from when the idle timer fires.
            gesture_interval_range_s: (min, max) seconds between gestures.
        """
        self.gesture_interval_range_s = gesture_interval_range_s
        self._behaviors = behaviors
        # Chosen on the first tick, once a robot connection is available.
        self._next_behavior: Optional[Move] = None
        self._next_interval_s = 0.0
        self._preparing: Optional[threading.Thread] = None

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
        if self._next_behavior is None:
            self._schedule_next_gesture(reachy_mini)

        if shared_state.seconds_since_last_activity() >= self._next_interval_s:
            self._play_next_gesture(reachy_mini)
            shared_state.mark_activity()
            return None

        return get_breathing_pose(t, antennas_enabled=antennas_enabled)

    def _schedule_next_gesture(self, reachy_mini: ReachyMini) -> None:
        """Pick the next gesture and its delay, and start uploading its sounds."""
        self._next_behavior = random.choice(self._behaviors)
        self._next_interval_s = random.uniform(*self.gesture_interval_range_s)
        self._preparing = threading.Thread(
            target=self._next_behavior.prepare, args=(reachy_mini,), daemon=True
        )
        self._preparing.start()

    def _play_next_gesture(self, reachy_mini: ReachyMini) -> None:
        """Play the scheduled gesture, once its sounds have finished uploading."""
        self._preparing.join()  # usually finished long ago
        self._next_behavior.play(reachy_mini)
        self._next_behavior = None
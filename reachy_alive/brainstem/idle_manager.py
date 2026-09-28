# reachy_alive/brainstem/idle_manager.py
"""Idle-behavior arbitration for the Brainstem."""

import logging
import random
import threading
from typing import List, Optional, Tuple

from reachy_mini import ReachyMini

from reachy_alive.brainstem.breathing import get_breathing_pose
from reachy_alive.commands import Command, HoldPose, PlayMove
from reachy_alive.moves.base import Move
from reachy_alive.shared_state import SharedState

logger = logging.getLogger(__name__)


class IdleManager:
    """Decides, each tick, between breathing and an occasional gesture.

    It never drives the robot: it returns a command that RobotManager
    executes. Gestures fire at random intervals; breathing runs the rest
    of the time. The next gesture is chosen in advance, so its sounds
    upload in the background while the robot is still breathing. The idle
    timer lives in SharedState so other decision-makers can reset it.
    """

    def __init__(
        self,
        behaviors: List[Move],
        gesture_interval_range_s: Tuple[float, float] = (20.0, 30.0),
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
        # When the current stretch of breathing began; None until the next tick.
        self._breathing_started_at_s: Optional[float] = None
        # Set when a gesture is handed off: the idle timer restarts on the
        # next call, once the gesture has finished playing.
        self._reset_idle_timer_next_tick = False

    def decide(
        self,
        t: float,
        shared_state: SharedState,
        reachy_mini: ReachyMini,
        antennas_enabled: bool = True,
    ) -> Command:
        """Return this tick's command: a breathing pose, or a gesture to play.

        Args:
            t: Elapsed time in seconds since the control loop started.
            shared_state: Read and reset the idle timer.
            reachy_mini: Robot instance, used only to upload the next
                gesture's sounds ahead of time.
            antennas_enabled: Whether antennas move during breathing.

        Returns:
            HoldPose while breathing, PlayMove when a gesture is due.
        """
        # PlayMove blocks the control loop until the gesture ends, so this
        # call only happens once it has finished. This relies on Move.play()
        # blocking: gestures running tick by tick will need an explicit
        # end-of-gesture signal instead.
        if self._reset_idle_timer_next_tick:
            shared_state.mark_activity()
            self._reset_idle_timer_next_tick = False

        if self._next_behavior is None:
            self._schedule_next_gesture(reachy_mini)

        if shared_state.seconds_since_last_activity() >= self._next_interval_s:
            return self._hand_off_next_gesture()

        if self._breathing_started_at_s is None:
            self._breathing_started_at_s = t
        breathing_t = t - self._breathing_started_at_s
        head, antennas = get_breathing_pose(breathing_t, antennas_enabled=antennas_enabled)
        return HoldPose(head=head, antennas=antennas)

    def _schedule_next_gesture(self, reachy_mini: ReachyMini) -> None:
        """Pick the next gesture and its delay, and start uploading its sounds."""
        self._next_behavior = random.choice(self._behaviors)
        self._next_interval_s = random.uniform(*self.gesture_interval_range_s)
        self._preparing = threading.Thread(
            target=self._next_behavior.prepare, args=(reachy_mini,), daemon=True
        )
        self._preparing.start()

    def _hand_off_next_gesture(self) -> PlayMove:
        """Hand the scheduled gesture over, once its sounds have finished uploading."""
        self._preparing.join()  # usually finished long ago
        logger.info("Playing %s", self._next_behavior.name)
        command = PlayMove(self._next_behavior)
        self._next_behavior = None
        # play() leaves the robot at neutral, and breathing starts there.
        self._breathing_started_at_s = None
        self._reset_idle_timer_next_tick = True
        return command
# reachy_alive/brainstem/idle_manager.py
"""Idle behavior for the Brainstem: breathing, with an idle move now and then."""

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
    """Decides, each tick, between breathing and an occasional idle move.

    It never drives the robot: it returns a command that RobotController
    executes. Idle moves fire at random intervals; breathing runs the rest
    of the time. The next idle move is chosen in advance, so its sounds
    upload in the background while the robot is still breathing. It only
    reads the idle timer: RobotController restarts it whenever a move ends.
    """

    def __init__(
        self,
        idle_moves: List[Move],
        idle_move_interval_range_s: Tuple[float, float] = (20.0, 30.0),
    ) -> None:
        """Set up the idle move pool.

        Args:
            idle_moves: Moves to pick from when the idle timer fires.
            idle_move_interval_range_s: (min, max) seconds between idle moves.
        """
        self.idle_move_interval_range_s = idle_move_interval_range_s
        self._idle_moves = idle_moves
        # Chosen on the first tick, once a robot connection is available.
        self._next_idle_move: Optional[Move] = None
        self._next_interval_s = 0.0
        self._preparing: Optional[threading.Thread] = None
        # When the current stretch of breathing began; None until the next tick.
        self._breathing_started_at_s: Optional[float] = None

    def decide(
        self, t: float, shared_state: SharedState, reachy_mini: ReachyMini
    ) -> Command:
        """Return this tick's command: a breathing pose, or an idle move to play.

        Args:
            t: Elapsed time in seconds since the control loop started.
            shared_state: Read the idle timer.
            reachy_mini: Robot instance, used only to upload the next idle
                move's sounds ahead of time.

        Returns:
            HoldPose while breathing, PlayMove when an idle move is due.
        """
        if self._next_idle_move is None:
            self._schedule_next_idle_move(reachy_mini)

        if shared_state.seconds_since_last_activity() >= self._next_interval_s:
            return self._hand_off_next_idle_move()

        if self._breathing_started_at_s is None:
            self._breathing_started_at_s = t
        breathing_t = t - self._breathing_started_at_s
        head, antennas = get_breathing_pose(breathing_t)
        return HoldPose(head=head, antennas=antennas)

    def interrupt(self) -> None:
        """Note that another action took over: breathing restarts from neutral."""
        self._breathing_started_at_s = None

    def _schedule_next_idle_move(self, reachy_mini: ReachyMini) -> None:
        """Pick the next idle move and its delay, and start uploading its sounds."""
        self._next_idle_move = random.choice(self._idle_moves)
        self._next_interval_s = random.uniform(*self.idle_move_interval_range_s)
        self._preparing = threading.Thread(
            target=self._next_idle_move.prepare, args=(reachy_mini,), daemon=True
        )
        self._preparing.start()

    def _hand_off_next_idle_move(self) -> PlayMove:
        """Hand the scheduled idle move over, once its sounds have finished uploading."""
        self._preparing.join()  # usually finished long ago
        logger.info("Playing %s", self._next_idle_move.name)
        command = PlayMove(self._next_idle_move)
        self._next_idle_move = None
        # play() leaves the robot at neutral, and breathing starts there.
        self._breathing_started_at_s = None
        return command
"""Idle behavior for the Brainstem: breathing, with an idle move now and then."""

import logging
import random
import threading
from typing import List, Optional

from reachy_mini import ReachyMini

from reachy_alive.brain.brainstem.breathing import get_breathing_pose
from reachy_alive.control.commands import Command, HoldPose, PlayMove
from reachy_alive.moves.base import Move
from reachy_alive.shared_state import SharedState

logger = logging.getLogger(__name__)


class IdleManager:
    """Decides, each tick, between breathing and an occasional idle move.

    It never drives the robot: it returns a command that RobotController
    executes. Idle moves fire at random intervals, within the range set in
    SharedState; breathing runs the rest of the time. The next idle move is
    chosen in advance, with its delay, so its sounds upload in the background
    while the robot is still breathing: a new range applies from the next
    idle move on. It only reads the idle timer: RobotController restarts it
    whenever a move ends.
    """

    def __init__(self, idle_moves: List[Move]) -> None:
        """Set up the idle move pool.

        Args:
            idle_moves: Moves to pick from when the idle timer fires.
        """
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
            shared_state: Read the idle timer and the idle move interval.
            reachy_mini: Robot instance, used only to upload the next idle
                move's sounds ahead of time.

        Returns:
            HoldPose while breathing, PlayMove when an idle move is due.
        """
        if self._next_idle_move is None:
            self._schedule_next_idle_move(shared_state, reachy_mini)

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

    def _schedule_next_idle_move(
        self, shared_state: SharedState, reachy_mini: ReachyMini
    ) -> None:
        """Pick the next idle move and its delay, and start uploading its sounds."""
        self._next_idle_move = random.choice(self._idle_moves)
        self._next_interval_s = random.uniform(*shared_state.idle_move_interval_range_s())
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
"""Chooses, each tick, which proposal the robot acts on."""

import logging
import queue

from reachy_mini import ReachyMini

from reachy_alive.brain.brainstem.breathing import get_breathing_pose
from reachy_alive.brain.brainstem.idle_manager import IdleManager
from reachy_alive.control.commands import Command, HoldPose, PlayMove
from reachy_alive.moves.base import Move
from reachy_alive.shared_state import SharedState

logger = logging.getLogger(__name__)


class ActionSelector:
    """Chooses, each tick, which proposal the robot acts on.

    A move requested from the app's page wins over an idle move. When nobody
    proposes a move, the robot breathes. If several requests arrive during
    one move, only the latest plays.
    """

    def __init__(self, idle_manager: IdleManager, move_requests: queue.Queue) -> None:
        """Keep where proposals come from.

        Args:
            idle_manager: Proposes an idle move now and then.
            move_requests: Moves requested from the app's page.
        """
        self._idle_manager = idle_manager
        self._move_requests = move_requests
        # When the current stretch of breathing began; None until the next tick.
        self._breathing_started_at_s: float | None = None

    def decide(
        self, t: float, shared_state: SharedState, reachy_mini: ReachyMini
    ) -> Command:
        """Return this tick's command.

        Args:
            t: Elapsed time in seconds since the control loop started.
            shared_state: Shared blackboard, passed through to IdleManager.
            reachy_mini: Robot instance, passed through to IdleManager.

        Returns:
            PlayMove for a requested move, otherwise for an idle move that is
            due, otherwise the breathing pose.
        """
        move = self._latest_requested_move()
        if move is not None:
            logger.info("Playing %s (requested)", move.name)
        else:
            move = self._idle_manager.propose(shared_state, reachy_mini)

        if move is not None:
            # Every move ends at neutral, where breathing starts.
            self._breathing_started_at_s = None
            return PlayMove(move)
        return self._breathe(t)

    def _latest_requested_move(self) -> Move | None:
        """Empty the request queue and return its latest move, if any."""
        latest = None
        while True:
            try:
                latest = self._move_requests.get_nowait()
            except queue.Empty:
                return latest

    def _breathe(self, t: float) -> HoldPose:
        """Return this tick's breathing pose, starting a new stretch after a move."""
        if self._breathing_started_at_s is None:
            self._breathing_started_at_s = t
        head, antennas = get_breathing_pose(t - self._breathing_started_at_s)
        return HoldPose(head=head, antennas=antennas)

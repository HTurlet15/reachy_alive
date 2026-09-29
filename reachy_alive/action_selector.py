"""Chooses, each tick, which proposal the robot acts on."""

import logging
import queue

from reachy_mini import ReachyMini

from reachy_alive.brainstem.idle_manager import IdleManager
from reachy_alive.commands import Command, PlayMove
from reachy_alive.moves.base import Move
from reachy_alive.shared_state import SharedState

logger = logging.getLogger(__name__)


class ActionSelector:
    """Chooses, each tick, which proposal the robot acts on.

    A move requested from the settings page wins over idle behavior.
    If several requests arrive during one move, only the latest plays.
    """

    def __init__(self, idle_manager: IdleManager, move_requests: queue.Queue) -> None:
        """
        Args:
            idle_manager: Proposes breathing and idle moves.
            move_requests: Moves requested from the settings page.
        """
        self._idle_manager = idle_manager
        self._move_requests = move_requests

    def decide(
        self,
        t: float,
        shared_state: SharedState,
        reachy_mini: ReachyMini,
        antennas_enabled: bool = True,
    ) -> Command:
        """Return this tick's command.

        Args:
            t: Elapsed time in seconds since the control loop started.
            shared_state: Shared blackboard, passed through to IdleManager.
            reachy_mini: Robot instance, passed through to IdleManager.
            antennas_enabled: Whether antennas move during breathing.

        Returns:
            PlayMove for the latest requested move, otherwise IdleManager's
            command.
        """
        requested_move = self._latest_requested_move()
        if requested_move is not None:
            logger.info("Playing %s (requested)", requested_move.name)
            self._idle_manager.interrupt()
            return PlayMove(requested_move)
        return self._idle_manager.decide(
            t, shared_state, reachy_mini, antennas_enabled=antennas_enabled
        )

    def _latest_requested_move(self) -> Move | None:
        """Empty the request queue and return its latest move, if any."""
        latest = None
        while True:
            try:
                latest = self._move_requests.get_nowait()
            except queue.Empty:
                return latest
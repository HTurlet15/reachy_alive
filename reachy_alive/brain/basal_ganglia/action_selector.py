"""Chooses, each tick, which move the robot starts next, if any."""

import logging
import queue

from reachy_alive.brain.brainstem.idle_manager import IdleManager
from reachy_alive.brain.cerebellum.move_player import MovePlayer
from reachy_alive.moves.base import Move

logger = logging.getLogger(__name__)


class ActionSelector:
    """Chooses which move the robot starts next; the MovePlayer plays it.

    A move plays to its end, then eases back to neutral. Only then is the
    next move chosen: a move requested from the app's page wins over an idle
    move, and if several requests arrived meanwhile, only the latest plays.
    When there is no move to play, the robot breathes; how long it has been
    breathing is what tells IdleManager whether an idle move is due.
    """

    def __init__(
        self, idle_manager: IdleManager, move_requests: queue.Queue, move_player: MovePlayer
    ) -> None:
        """Keep where proposals come from, and the MovePlayer it asks.

        Args:
            idle_manager: Proposes an idle move now and then.
            move_requests: Moves requested from the app's page.
            move_player: Asked whether it is busy, and how long the robot has
                been resting. The selector never plays a move itself.
        """
        self._idle_manager = idle_manager
        self._move_requests = move_requests
        self._move_player = move_player

    def choose(self, now: float) -> Move | None:
        """Return the move to start now, highest priority first; None if there is none.

        An order for this tick only: the control loop hands it to the
        MovePlayer, which keeps what is playing. So the selector asks it
        whether it is busy, and chooses again only once it is free.

        Args:
            now: This tick's time.monotonic() reading.
        """
        # 1. A move, or its way back to neutral, is playing: it goes on to its end.
        if self._move_player.is_busy(now):
            return None

        # 2. A move was requested from the app's page: play the latest one.
        requested = self._latest_requested_move()
        if requested is not None:
            logger.info("Playing %s (requested)", requested.name)
            return requested

        # 3. The robot has rested long enough: an idle move, otherwise None to breathe.
        return self._idle_manager.propose(self._move_player.resting_for_s(now))

    def _latest_requested_move(self) -> Move | None:
        """Empty the request queue and return its latest move, if any."""
        latest = None
        while True:
            try:
                latest = self._move_requests.get_nowait()
            except queue.Empty:
                return latest

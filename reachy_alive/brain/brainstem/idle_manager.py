"""Idle behavior for the Brainstem: an idle move now and then."""

import logging
import random

from reachy_alive.moves.base import Move
from reachy_alive.shared_state import SharedState

logger = logging.getLogger(__name__)


class IdleManager:
    """Proposes, now and then, an idle move.

    It never drives the robot: it hands a move to the ActionSelector, which
    has the MovePlayer play it, and proposes nothing the rest of the time. Idle moves come at
    random intervals, within the range set in SharedState. Each delay is
    drawn as soon as it starts running: a new range applies from the next
    idle move on. It reads no clock: the ActionSelector tells it how long the
    robot has been resting, as the MovePlayer counts it.
    """

    def __init__(self, idle_moves: list[Move], shared_state: SharedState) -> None:
        """Set up the idle move pool.

        Args:
            idle_moves: Moves to pick from when an idle move is due.
            shared_state: Read the idle move interval.
        """
        self._idle_moves = idle_moves
        self._shared_state = shared_state
        # Drawn on the first tick, then again after each idle move.
        self._delay_s: float | None = None

    def propose(self, resting_for_s: float) -> Move | None:
        """Return an idle move if one is due now.

        Args:
            resting_for_s: How long the robot has been resting, since its
                last move ended.

        Returns:
            A random idle move once the delay has run out, otherwise None.
        """
        if self._delay_s is None:
            self._delay_s = random.uniform(*self._shared_state.idle_move_interval_range_s())

        if resting_for_s < self._delay_s:
            return None

        self._delay_s = None
        move = random.choice(self._idle_moves)
        logger.info("Playing %s", move.name)
        return move

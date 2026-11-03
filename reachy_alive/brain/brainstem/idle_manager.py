"""Idle behavior for the Brainstem: an idle move now and then."""

import logging
import random
import threading

from reachy_mini import ReachyMini

from reachy_alive.moves.base import Move
from reachy_alive.shared_state import SharedState

logger = logging.getLogger(__name__)


class IdleManager:
    """Proposes, now and then, an idle move.

    It never drives the robot: it hands a move to the ActionSelector, which
    plays it, and proposes nothing the rest of the time. Idle moves
    come at random intervals, within the range set in SharedState. The next
    idle move is chosen in advance, with its delay, so its sounds upload in
    the background while the robot is still breathing: a new range applies
    from the next idle move on. It only reads the idle timer: RobotController
    restarts it whenever a move ends.
    """

    def __init__(self, idle_moves: list[Move]) -> None:
        """Set up the idle move pool.

        Args:
            idle_moves: Moves to pick from when the idle timer fires.
        """
        self._idle_moves = idle_moves
        # Chosen on the first tick, once a robot connection is available.
        self._next_idle_move: Move | None = None
        self._next_interval_s = 0.0
        self._preparing: threading.Thread | None = None

    def propose(self, shared_state: SharedState, reachy_mini: ReachyMini) -> Move | None:
        """Return the idle move due now, if any.

        Args:
            shared_state: Read the idle timer and the idle move interval.
            reachy_mini: Robot instance, used only to upload the next idle
                move's sounds ahead of time.

        Returns:
            The idle move to play, or None while it isn't due yet.
        """
        if self._next_idle_move is None:
            self._schedule_next_idle_move(shared_state, reachy_mini)

        if shared_state.seconds_since_last_activity() >= self._next_interval_s:
            return self._hand_off_next_idle_move()
        return None

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

    def _hand_off_next_idle_move(self) -> Move:
        """Hand the scheduled idle move over, once its sounds have finished uploading."""
        self._preparing.join()  # usually finished long ago
        logger.info("Playing %s", self._next_idle_move.name)
        move = self._next_idle_move
        self._next_idle_move = None
        return move

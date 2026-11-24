"""Chooses, each tick, which move the robot starts next, if any."""

import logging
import queue

from reachy_alive.brain.basal_ganglia.proposal import Proposal
from reachy_alive.brain.brainstem.idle_manager import IdleManager
from reachy_alive.brain.brainstem.reflexes.reflex_manager import ReflexManager
from reachy_alive.brain.cerebellum.motion_generator import MotionGenerator

logger = logging.getLogger(__name__)


class ActionSelector:
    """Chooses which move the robot starts next; the MotionGenerator plays it.

    A move plays to its end, then eases back to neutral. Only then is the
    next move chosen: a reflex wins over a move requested from the app's page,
    which wins over an idle move; if several requests arrived meanwhile, only
    the latest plays.
    When there is no move to play, the robot breathes; how long it has been
    breathing is what tells IdleManager whether an idle move is due.
    """

    def __init__(
        self,
        reflex_manager: ReflexManager,
        idle_manager: IdleManager,
        move_requests: queue.Queue,
        motion_generator: MotionGenerator,
    ) -> None:
        """Keep where proposals come from, and the MotionGenerator it asks.

        Args:
            reflex_manager: Proposes what a reflex reacts with, if any.
            idle_manager: Proposes an idle move now and then.
            move_requests: The app's page's proposals, in the order clicked.
            motion_generator: Asked whether it is busy, and how long the robot has
                been resting. The selector never plays a move itself.
        """
        self._reflex_manager = reflex_manager
        self._idle_manager = idle_manager
        self._move_requests = move_requests
        self._motion_generator = motion_generator

    def choose(self, now: float) -> Proposal | None:
        """Return the proposal chosen this tick, highest priority first; None if there is none.

        An order for this tick only: the control loop hands it to the
        MotionGenerator, which keeps what is playing. So the selector asks it
        whether it is busy, and chooses again only once it is free.

        Args:
            now: This tick's time.monotonic() reading.
        """
        # 1. A move, or its way back to neutral, is playing: it goes on to its end.
        if self._motion_generator.is_busy(now):
            return None

        # 2. A reflex reacts to what the senses just perceived.
        proposal = self._reflex_manager.propose(now)
        if proposal is not None:
            logger.info("Reacting: %s", proposal)
            return proposal

        # 3. The app's page proposed a move: the latest one.
        proposal = self._latest_page_proposal()
        if proposal is not None:
            logger.info("Playing %s (requested)", proposal.move_to_start.name)
            return proposal

        # 4. The robot has rested long enough: an idle move, otherwise None to breathe.
        return self._idle_manager.propose(self._motion_generator.resting_for_s(now))

    def _latest_page_proposal(self) -> Proposal | None:
        """Empty the page's queue and return its latest proposal, if any."""
        latest = None
        while True:
            try:
                latest = self._move_requests.get_nowait()
            except queue.Empty:
                return latest

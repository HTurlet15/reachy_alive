"""Asks the reflexes, in order of priority, whether one reacts."""

from reachy_alive.brain.basal_ganglia.proposal import Proposal


class ReflexManager:
    """Asks its reflexes in order of priority; the first one that proposes wins.

    Two reflexes may react on the same tick, and only one proposal goes on to
    the ActionSelector: the order decides, and it is set in one place, where
    the manager is built. A reflex that loses is asked again on the next tick.
    """

    def __init__(self, reflexes: list) -> None:
        """Keep the reflexes to ask.

        Args:
            reflexes: Most urgent first. Each has a `propose(now)` method that
                returns a Proposal, or None while it has nothing to react to.
        """
        self._reflexes = reflexes

    def propose(self, now: float) -> Proposal | None:
        """Return the most urgent reflex's proposal this tick, or None if none reacts.

        Args:
            now: This tick's time.monotonic() reading.
        """
        for reflex in self._reflexes:
            proposal = reflex.propose(now)
            if proposal is not None:
                return proposal
        return None

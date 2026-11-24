"""Unit tests for ReflexManager: the most urgent reflex that reacts wins."""

from reachy_alive.brain.basal_ganglia.proposal import Direction, Proposal
from reachy_alive.brain.brainstem.reflexes.reflex_manager import ReflexManager

LOOK_LEFT = Proposal(source="look", direction=Direction(yaw_rad=0.5, duration_s=1.0))
LOOK_RIGHT = Proposal(source="other look", direction=Direction(yaw_rad=-0.5, duration_s=1.0))


class Reflex:
    """A reflex that proposes the same thing on every tick, and counts how often it was asked."""

    def __init__(self, proposal):
        self.proposal = proposal
        self.asked = 0

    def propose(self, now):
        self.asked += 1
        return self.proposal


def test_without_reflexes_nothing_is_proposed():
    assert ReflexManager([]).propose(now=1.0) is None


def test_the_first_reflex_that_reacts_wins():
    quiet, urgent, basic = Reflex(None), Reflex(LOOK_LEFT), Reflex(LOOK_RIGHT)

    proposal = ReflexManager([quiet, urgent, basic]).propose(now=1.0)

    assert proposal is LOOK_LEFT
    assert basic.asked == 0  # asked again on the next tick

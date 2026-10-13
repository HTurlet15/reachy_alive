"""Bumps: a knock on the robot, or on its table, felt through the inertial unit."""

import logging
import math

from reachy_alive.brain.sensory_cortex.inertial.inertial_frame import InertialFrame
from reachy_alive.shared_state import InertialFacts

logger = logging.getLogger(__name__)


class BumpDetector:
    """Spots bumps: readings whose acceleration strays from gravity.

    The acceleration's norm doesn't depend on how the head is tilted. A bump
    makes the head ring for a few readings, so the readings right after it
    are ignored.
    """

    GRAVITY_M_S2 = 9.81
    # How far from gravity the acceleration must stray.
    THRESHOLD_M_S2 = 2.5
    # How long readings are ignored after a bump, while the head rings.
    REFRACTORY_S = 0.3

    def __init__(self, facts: InertialFacts) -> None:
        self._facts = facts
        self._ignore_until = -math.inf

    def update(self, frame: InertialFrame) -> None:
        """Read one frame, and record a bump if one starts on it."""
        if frame.robot_moving_itself or frame.t < self._ignore_until:
            return
        if not self._strays_from_gravity(frame.accelerometer):
            return
        self._ignore_until = frame.t + self.REFRACTORY_S
        self._facts.record_bump(frame.t)
        logger.info("Bump")

    def _strays_from_gravity(self, accelerometer: tuple[float, float, float]) -> bool:
        return abs(math.hypot(*accelerometer) - self.GRAVITY_M_S2) >= self.THRESHOLD_M_S2

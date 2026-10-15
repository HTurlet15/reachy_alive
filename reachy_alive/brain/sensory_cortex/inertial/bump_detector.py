"""Bumps: a knock on the robot, or on its table, felt through the inertial unit."""

import logging
import math

from reachy_alive.brain.sensory_cortex.detector import Detector
from reachy_alive.brain.sensory_cortex.inertial.inertial_features import InertialFeatures
from reachy_alive.shared_state import InertialFacts

logger = logging.getLogger(__name__)


class BumpDetector(Detector):
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
        super().__init__(facts)
        self._ignore_until = -math.inf

    def _detect(self, features: InertialFeatures) -> None:
        """Record a bump if one starts on this reading."""
        if features.t < self._ignore_until:
            return
        if not self._strays_from_gravity(features.accelerometer):
            return
        self._ignore_until = features.t + self.REFRACTORY_S
        self._facts.record_bump(features.t)
        logger.info("Bump")

    def _strays_from_gravity(self, accelerometer: tuple[float, float, float]) -> bool:
        return abs(math.hypot(*accelerometer) - self.GRAVITY_M_S2) >= self.THRESHOLD_M_S2
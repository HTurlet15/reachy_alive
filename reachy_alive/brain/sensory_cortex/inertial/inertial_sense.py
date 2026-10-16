"""The inertial sense: what the inertial unit feels, 50 times a second."""

import logging

from reachy_mini import ReachyMini

from reachy_alive.brain.sensory_cortex.inertial.inertial_features import InertialFeatures
from reachy_alive.brain.sensory_cortex.sense import Sense
from reachy_alive.shared_state import SharedState

logger = logging.getLogger(__name__)


class InertialSense(Sense):
    """Reads the inertial unit and describes each reading by its InertialFeatures.

    It counts as available even in simulation: the SDK gives no data until
    the first reading, so it can't tell yet.
    """

    # The SDK refreshes the inertial unit 50 times a second: reading faster
    # would only read each sample twice.
    PERIOD_S = 0.02

    def __init__(self, reachy_mini: ReachyMini, shared_state: SharedState) -> None:
        """Keep what the sense reads from, with no missing data reported yet."""
        super().__init__(reachy_mini, shared_state)
        self._reported_missing_data = False

    def _perceive(self, perceived_at: float, robot_moving_itself: bool) -> InertialFeatures | None:
        """Describe the latest reading, or return None if the inertial unit gives none."""
        reading = self._reachy_mini.imu
        if reading is None:
            if not self._reported_missing_data:
                logger.info("No inertial unit data: nothing will be felt")
                self._reported_missing_data = True
            return None
        return InertialFeatures(
            perceived_at=perceived_at,
            accelerometer=tuple(reading["accelerometer"]),
            robot_moving_itself=robot_moving_itself,
        )

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
        super().__init__(reachy_mini, shared_state)
        self._said_no_data = False

    def _perceive(self, t: float, robot_moving_itself: bool) -> InertialFeatures | None:
        """Describe the latest reading, or return None if the inertial unit gives none."""
        reading = self._reachy_mini.imu
        if reading is None:
            self._say_once_there_is_no_data()
            return None
        return InertialFeatures(
            t=t,
            accelerometer=tuple(reading["accelerometer"]),
            robot_moving_itself=robot_moving_itself,
        )

    def _say_once_there_is_no_data(self) -> None:
        if not self._said_no_data:
            logger.info("No inertial unit data: nothing will be felt")
            self._said_no_data = True
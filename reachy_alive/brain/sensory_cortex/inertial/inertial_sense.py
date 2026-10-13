"""The inertial sense: what the inertial unit feels, as an InertialFrame 50 times a second."""

import logging

from reachy_mini import ReachyMini

from reachy_alive.brain.sensory_cortex.inertial.inertial_frame import InertialFrame
from reachy_alive.brain.sensory_cortex.sense import Sense
from reachy_alive.shared_state import SharedState

logger = logging.getLogger(__name__)


class InertialSense(Sense):
    """Reads the inertial unit and describes each reading as an InertialFrame.

    It counts as available even in simulation: the SDK gives no data until
    the first reading, so it can't tell yet.
    """

    # The SDK refreshes the inertial unit 50 times a second: reading faster
    # would only read each sample twice.
    PERIOD_S = 0.02
    # The head still rings this long after a move ends.
    SETTLE_AFTER_MOVE_S = 0.5

    def __init__(self, reachy_mini: ReachyMini, shared_state: SharedState) -> None:
        """Keep what the sense reads from.

        Args:
            reachy_mini: Connected robot instance, only read.
            shared_state: Where the sense learns whether the robot is moving itself.
        """
        self._reachy_mini = reachy_mini
        self._shared_state = shared_state
        self._said_no_data = False

    def read_once(self, now: float) -> InertialFrame | None:
        """Describe the latest reading, or return None if the inertial unit gives none.

        Args:
            now: Time of the reading, in seconds, on time.monotonic()'s clock.
        """
        reading = self._reachy_mini.imu
        if reading is None:
            self._say_once_there_is_no_data()
            return None
        return InertialFrame(
            t=now,
            accelerometer=tuple(reading["accelerometer"]),
            robot_moving_itself=self._robot_moves_itself(),
        )

    def _say_once_there_is_no_data(self) -> None:
        if not self._said_no_data:
            logger.info("No inertial unit data: nothing will be felt")
            self._said_no_data = True

    def _robot_moves_itself(self) -> bool:
        """Whether a move plays, or ended too recently for the head to be still."""
        return (
            self._shared_state.is_move_playing()
            or self._shared_state.seconds_since_last_activity() < self.SETTLE_AFTER_MOVE_S
        )
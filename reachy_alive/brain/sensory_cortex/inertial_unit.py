"""Touch felt through the inertial unit: a knock on the robot, or on its table."""

import logging
import math
import threading
import time

from reachy_mini import ReachyMini

from reachy_alive.shared_state import SharedState

logger = logging.getLogger(__name__)

GRAVITY_M_S2 = 9.81


class BumpDetector:
    """Spots bumps in a stream of accelerometer readings.

    A bump is a reading whose acceleration norm strays from gravity by more
    than a threshold. The norm doesn't depend on how the head is tilted.
    A bump makes the head ring for a few readings, so the readings right
    after it are ignored for a refractory period.

    Attributes:
        threshold_m_s2: How far from gravity the norm must stray, in m/s².
        refractory_s: How long readings are ignored after a bump, in seconds.
    """

    def __init__(self, threshold_m_s2: float = 2.5, refractory_s: float = 0.3) -> None:
        """
        Args:
            threshold_m_s2: How far from gravity the norm must stray, in m/s².
            refractory_s: How long readings are ignored after a bump, in seconds.
        """
        self.threshold_m_s2 = threshold_m_s2
        self.refractory_s = refractory_s
        self._ignore_until = -math.inf

    def update(self, t: float, accelerometer: tuple[float, float, float]) -> bool:
        """Read one accelerometer sample.

        Args:
            t: Time of the reading, in seconds, on a clock that only goes
                forward.
            accelerometer: (x, y, z) acceleration, in m/s².

        Returns:
            True if this reading starts a new bump.
        """
        if t < self._ignore_until:
            return False
        if abs(math.hypot(*accelerometer) - GRAVITY_M_S2) < self.threshold_m_s2:
            return False
        self._ignore_until = t + self.refractory_s
        return True


class InertialUnitSense:
    """Reads the inertial unit and records bumps in SharedState.

    Runs in its own thread, never drives the robot. It ignores what it feels
    while a move plays and for a short while after it ends: the robot's own
    motion would read as bumps.

    Attributes:
        read_period_s: Time between two readings, in seconds.
        settle_after_move_s: How long bumps are still ignored after a move
            ends, in seconds.
    """

    def __init__(
        self,
        reachy_mini: ReachyMini,
        shared_state: SharedState,
        bump_detector: BumpDetector | None = None,
        read_period_s: float = 0.01,
        settle_after_move_s: float = 0.5,
    ) -> None:
        """
        Args:
            reachy_mini: Connected robot instance, only read from.
            shared_state: Where bumps are recorded, and where the sense learns
                whether the robot is moving.
            bump_detector: Spots bumps in the readings.
            read_period_s: Time between two readings, in seconds.
            settle_after_move_s: How long bumps are still ignored after a move
                ends, in seconds.
        """
        self._reachy_mini = reachy_mini
        self._shared_state = shared_state
        self._bump_detector = bump_detector or BumpDetector()
        self.read_period_s = read_period_s
        self.settle_after_move_s = settle_after_move_s
        self._said_no_inertial_unit = False

    def run(self, stop_event: threading.Event) -> None:
        """Read the inertial unit until stop_event is set.

        Args:
            stop_event: Set externally to stop the sense.
        """
        while not stop_event.wait(self.read_period_s):
            self.read_once(time.monotonic())

    def read_once(self, now: float) -> None:
        """Take one reading, and record a bump if it is one.

        Args:
            now: Time of the reading, in seconds, on time.monotonic()'s clock.
        """
        reading = self._reachy_mini.imu
        if reading is None:
            if not self._said_no_inertial_unit:
                logger.info("No inertial unit data: bumps won't be sensed")
                self._said_no_inertial_unit = True
            return
        if self._robot_moves_itself():
            return
        if self._bump_detector.update(now, tuple(reading["accelerometer"])):
            self._shared_state.record_bump(now)
            logger.info("Bump")

    def _robot_moves_itself(self) -> bool:
        """Whether a move plays, or ended too recently for the head to be still."""
        return (
            self._shared_state.is_move_playing()
            or self._shared_state.seconds_since_last_activity() < self.settle_after_move_s
        )
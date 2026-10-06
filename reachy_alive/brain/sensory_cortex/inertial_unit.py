"""Touch felt through the inertial unit: a knock on the robot, or on its table."""

import math

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
        self._last_bump_at: float | None = None

    def update(self, t: float, accelerometer: tuple[float, float, float]) -> bool:
        """Read one accelerometer sample.

        Args:
            t: Time of the reading, in seconds, on a clock that only goes
                forward.
            accelerometer: (x, y, z) acceleration, in m/s².

        Returns:
            True if this reading starts a new bump.
        """
        if self._last_bump_at is not None and t - self._last_bump_at < self.refractory_s:
            return False
        if abs(math.hypot(*accelerometer) - GRAVITY_M_S2) < self.threshold_m_s2:
            return False
        self._last_bump_at = t
        return True

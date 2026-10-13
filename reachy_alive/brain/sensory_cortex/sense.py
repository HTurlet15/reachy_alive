"""Sense: the contract every sense follows, so that SenseManager can run any of them."""

from abc import ABC, abstractmethod


class Sense(ABC):
    """Reads one sensor and describes what it perceives as frames.

    SenseManager opens it, calls read_once every PERIOD_S until the app stops,
    then closes it. A sense never drives the robot, and knows nothing of the
    detectors that read its frames. A new sense writes read_once, and only
    the rest it needs.
    """

    # Time between two readings. 0: as fast as the sensor gives data.
    PERIOD_S = 0.0

    def is_available(self) -> bool:
        """Return whether the sensor can be read at all. By default, it can."""
        return True

    def open(self) -> None:
        """Get the sensor ready, before the first reading. By default, nothing to do."""

    def close(self) -> None:
        """Release the sensor, after the last reading. By default, nothing to do."""

    @abstractmethod
    def read_once(self, now: float):
        """Describe the sensor's latest data as a frame, or return None if there is none.

        Args:
            now: Time of the reading, in seconds, on time.monotonic()'s clock.
        """

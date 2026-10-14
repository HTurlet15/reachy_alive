"""Sense: the contract every sense follows, so that SenseManager can run any of them."""

from abc import ABC

from reachy_mini import ReachyMini

from reachy_alive.shared_state import SharedState


class Sense(ABC):
    """Reads one sensor and describes each reading by its features.

    SenseManager opens it, calls read_once every PERIOD_S until the app stops,
    then closes it, and hands the features to the sense's detectors. To write
    a sense, write _perceive. A sense never drives the robot, and knows
    nothing of its detectors.
    """

    # Time between two readings. 0: as fast as the sensor gives data.
    PERIOD_S = 0.0
    # How long after a move the robot may still perceive itself: the head
    # still rings, the antennas still settle.
    SETTLE_AFTER_MOVE_S = 0.5

    def __init__(self, reachy_mini: ReachyMini, shared_state: SharedState) -> None:
        """Keep what the sense reads from.

        Args:
            reachy_mini: Connected robot instance, only read.
            shared_state: Where the sense learns whether the robot is moving itself.
        """
        self._reachy_mini = reachy_mini
        self._shared_state = shared_state

    def is_available(self) -> bool:
        """Return whether the sensor can be read at all. By default, it can."""
        return True

    def open(self) -> None:
        """Get the sensor ready, before the first reading. By default, nothing to do."""

    def close(self) -> None:
        """Release the sensor, after the last reading. By default, nothing to do."""

    def read_once(self, now: float):
        """Read the sensor once, and return its features, or None if it gave nothing new.

        Args:
            now: Time of the reading, in seconds, on time.monotonic()'s clock.
        """
        return self._perceive(t=now, robot_moving_itself=self._robot_moving_itself(now))

    def _perceive(self, t: float, robot_moving_itself: bool):
        """Read the sensor, and return its features, or None if it gave nothing new.

        Every sense writes it, and defines its features in its own folder:
        VisionFeatures for the vision sense, for example. Only describes what
        the sensor gives: what it means is for the detectors to decide.

        Args:
            t: Time of the reading, to give the features: facts are dated with it.
            robot_moving_itself: Whether a move plays, or ended too recently for
                the robot to be still, to give the features: the sense may
                perceive the robot itself.
        """
        raise NotImplementedError  # abstract once every sense writes it

    def _robot_moving_itself(self, now: float) -> bool:
        """Whether a move plays, or ended less than SETTLE_AFTER_MOVE_S before `now`."""
        if self._shared_state.is_move_playing():
            return True
        ended_at = self._shared_state.last_move_ended_at()
        return ended_at is not None and now - ended_at < self.SETTLE_AFTER_MOVE_S
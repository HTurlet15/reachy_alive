"""Sense: the contract every sense follows, so that SenseManager can run any of them."""

from abc import ABC, abstractmethod

from reachy_mini import ReachyMini

from reachy_alive.shared_state import SharedState


class Sense(ABC):
    """Reads one sensor and describes each reading by its features.

    SenseManager calls perceive every PERIOD_S until the app stops, and hands
    the features to the sense's detectors. While the page has the sense
    switched off, perceive isn't called. To write a sense, give it a NAME and
    write _extract_features: read the sensor, and describe what it gives as
    features. A sense never drives the robot, and knows nothing of its
    detectors.
    """

    # What the page calls the sense, to switch it off: "vision", for example.
    NAME: str
    # Parts of the sense the page switches off one by one, such as each antenna
    # of the touch sense. Without any, the sense is switched off as a whole.
    PARTS: tuple[str, ...] = ()

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

    def names(self) -> list[str]:
        """Return what the page can switch off: the sense, or each of its parts.

        A part is named after the sense: "touch.right" for the right antenna.
        """
        if not self.PARTS:
            return [self.NAME]
        return [f"{self.NAME}.{part}" for part in self.PARTS]

    def is_enabled(self) -> bool:
        """Return whether the sense should run: until the page switches it off, or all its parts."""
        return any(self._shared_state.is_sense_enabled(name) for name in self.names())

    def perceive(self, now: float):
        """Return the features of one reading, or None if the sensor gave nothing new.

        Works out here, the same way for every sense, whether the robot is
        moving itself, then lets the sense extract its features.

        Args:
            now: Time of the reading, in seconds, on time.monotonic()'s clock.
        """
        return self._extract_features(
            perceived_at=now, robot_moving_itself=self._robot_moving_itself(now)
        )

    @abstractmethod
    def _extract_features(self, perceived_at: float, robot_moving_itself: bool):
        """Read the sensor, and describe what it gives as features, or return None if nothing new.

        Every sense writes it, and defines its features in its own folder:
        VisionFeatures for the vision sense, for example. Only describes what
        the sensor gives: what it means is for the detectors to decide.

        Args:
            perceived_at: Time of the reading, to give the features: every fact a
                detector records from them is dated with it.
            robot_moving_itself: Whether a move plays, or ended too recently for
                the robot to be still, to give the features: the sense may
                perceive the robot itself.
        """

    def _robot_moving_itself(self, now: float) -> bool:
        """Whether a move plays, or ended less than SETTLE_AFTER_MOVE_S before `now`."""
        if self._shared_state.is_move_playing():
            return True
        ended_at = self._shared_state.last_move_ended_at()
        return ended_at is not None and now - ended_at < self.SETTLE_AFTER_MOVE_S

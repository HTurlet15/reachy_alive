"""Detector: the contract every detector follows, and the tools detectors share.

SenseManager can feed any Detector. SchmittTrigger is an on/off state that
doesn't flicker, for detectors that follow one.
"""

from abc import ABC, abstractmethod


class Detector(ABC):
    """Reads the features of one sense, and records what they mean as facts.

    SenseManager builds it with its sense's facts, and hands it the features
    of every reading. To write a detector, write _detect: this class hands it
    the features of the readings the robot didn't disturb. The others go to
    _while_robot_moves, which ignores them unless overridden.
    """

    def __init__(self, facts) -> None:
        """Keep where the detector records its facts.

        Args:
            facts: Its sense's facts in SharedState, such as `shared_state.vision`.
        """
        self._facts = facts

    def update(self, features) -> None:
        """Read the features of one reading of the sense."""
        if features.robot_moving_itself:
            self._while_robot_moves(features)
        else:
            self._detect(features)

    @abstractmethod
    def _detect(self, features) -> None:
        """Read the features of an undisturbed reading, and record the facts they show."""

    def _while_robot_moves(self, features) -> None:
        """Read the features of a reading the robot disturbed. Ignores them by default.

        Override it when the detector must keep following its sensor even
        then, without recording facts: a background level, for example.
        """


class SchmittTrigger:
    """Turns on when a value reaches one threshold, and off only under a lower one.

    A single threshold would flicker while the value wavers around it: two
    thresholds keep the state steady, like the comparator of the same name in
    electronics.

    Attributes:
        on_since: When it last turned on, or None while it is off.
    """

    def __init__(self, on_threshold: float, off_threshold: float) -> None:
        """Set the two thresholds.

        Args:
            on_threshold: Turns on once the value reaches it.
            off_threshold: Turns off once the value falls under it.

        Raises:
            ValueError: If off_threshold is above on_threshold.
        """
        if off_threshold > on_threshold:
            raise ValueError(f"off_threshold {off_threshold} is above on_threshold {on_threshold}")
        self._on_threshold = on_threshold
        self._off_threshold = off_threshold
        self.on_since: float | None = None

    def is_on(self) -> bool:
        """Return whether it is on."""
        return self.on_since is not None

    def would_turn_on(self, value: float) -> bool:
        """Return whether this value would turn it on: it is off, and the value is high enough."""
        return not self.is_on() and value >= self._on_threshold

    def update(self, t: float, value: float) -> None:
        """Turn on or off with a new value.

        Args:
            t: Time of the value, in seconds, on a clock that only goes forward.
            value: The value followed.
        """
        if self.would_turn_on(value):
            self.on_since = t
        elif self.is_on() and value < self._off_threshold:
            self.on_since = None
            
"""Detector: the contract every detector follows, and the tools detectors share.

SenseManager can feed any Detector. SchmittTrigger is an on/off state that
doesn't flicker. Background is the level a signal has held lately, for
detectors that spot what stands out from it.
"""

import math
from abc import ABC, abstractmethod


class Detector(ABC):
    """Reads the features of one sense, and records what they mean as facts.

    SenseManager builds it with its sense's facts, and hands it the features
    of every reading. To write a detector, subclass it in a `*_detector.py`
    file of its sense's folder, where SenseManager finds it, and write
    _detect: this class hands it the features of the readings the robot
    didn't disturb. The others go to _while_robot_moves, which ignores them
    unless overridden. Write forget too, and call it from __init__: a new
    detector is one that just forgot. SenseManager calls it while the page
    has the sense switched off.
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

    @abstractmethod
    def forget(self) -> None:
        """Forget what is going on, as if just built: call it from __init__ too.

        SenseManager calls it while the page has the sense switched off.

        Clear the facts of anything going on, such as an antenna pushed: the
        sense can no longer tell whether it still is. Keep past events, such
        as the last bump: they stay true.
        """

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
            t: Time of the value, in seconds, on a monotonic clock.
            value: The value followed.
        """
        if self.would_turn_on(value):
            self.on_since = t
        elif self.is_on() and value < self._off_threshold:
            self.on_since = None


class Background:
    """The level a signal has held lately: what a sudden change stands out from.

    It follows the signal like a capacitor charging through a resistor: after
    one time constant, it has covered 63% of the way to a new level. The
    first value followed is taken as the background.
    """

    def __init__(self, time_constant_s: float) -> None:
        """Set how fast the background follows the signal.

        Args:
            time_constant_s: Short to follow quickly, long to follow slowly.
        """
        self._time_constant_s = time_constant_s
        self._level: float | None = None  # None until a first value is followed
        self._updated_at = -math.inf

    def height_of(self, value: float) -> float:
        """Return how far a value stands above the background: 0 until it has a level."""
        if self._level is None:
            return 0.0  # nothing to stand out from yet
        return value - self._level

    def follow(self, t: float, value: float) -> None:
        """Move a step toward a value, as far as the time since the last step allows.

        Args:
            t: Time of the value, in seconds, on a monotonic clock.
            value: The value followed.
        """
        if self._level is None:
            self._level = value
        else:
            elapsed_s = t - self._updated_at
            smoothing_factor = 1.0 - math.exp(-elapsed_s / self._time_constant_s)
            self._level += smoothing_factor * (value - self._level)
        self._updated_at = t

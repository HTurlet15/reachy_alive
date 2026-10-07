"""Touch felt through the antennas: someone pushing one away from where it was sent."""

import math
from collections import deque

import numpy as np


class AntennaPushDetector:
    """Spots when someone pushes one antenna away from where it was sent.

    The motor follows its target with a short delay: an antenna sent to 10°
    at 1.00 s only reaches 10° around 1.08 s. So at time t, the antenna
    isn't expected at the target just sent, but at the target sent
    `delay_s` earlier:

        time sent        1.00   1.02   1.04   1.06   1.08   1.10
        target           10°    11°    12°    13°    14°    15°
                                 ↑
        at t = 1.10 s, with delay_s = 0.08, the antenna is expected at
        the target sent at 1.02 s: 11°, not 15°.

    The gap is how far the measured position is from that expected one.
    A push starts when the gap reaches `push_threshold_deg`, and ends once
    it falls back under `release_threshold_deg`: with two thresholds, a gap
    hovering around one value doesn't flicker between pushed and released.

    One detector watches one antenna.

    Attributes:
        push_threshold_deg: Gap at which a push starts, in degrees.
        release_threshold_deg: Gap under which a push ends, in degrees.
        delay_s: How far behind its target the motor runs, in seconds.
    """

    def __init__(
        self,
        push_threshold_deg: float = 5.0,
        release_threshold_deg: float = 3.0,
        delay_s: float = 0.08,
    ) -> None:
        """
        Args:
            push_threshold_deg: Gap at which a push starts, in degrees.
            release_threshold_deg: Gap under which a push ends, in degrees.
            delay_s: How far behind its target the motor runs, in seconds.
        """
        self.push_threshold_deg = push_threshold_deg
        self.release_threshold_deg = release_threshold_deg
        self.delay_s = delay_s
        # The targets of the last moments, oldest first: when each was sent,
        # and where it sent the antenna.
        self._target_times: deque[float] = deque()
        self._target_angles_rad: deque[float] = deque()
        self._pushed_since: float | None = None

    def update(self, t: float, target_rad: float, present_rad: float) -> float | None:
        """Read one sample of the antenna.

        Args:
            t: Time of the sample, in seconds, on a clock that only goes
                forward.
            target_rad: Where the antenna was sent, in radians.
            present_rad: Where the antenna is, measured, in radians.

        Returns:
            When the current push started, or None if the antenna isn't
            pushed.
        """
        self._remember_target(t, target_rad)
        # Where the antenna should be now if nobody touches it: the target
        # it was sent delay_s ago, which the motor is only reaching now.
        delayed_target_rad = self._target_at(t - self.delay_s)
        if delayed_target_rad is None:
            return self._pushed_since  # not enough history yet to judge

        gap_deg = abs(math.degrees(present_rad - delayed_target_rad))
        if self._pushed_since is None and gap_deg >= self.push_threshold_deg:
            self._pushed_since = t
        elif self._pushed_since is not None and gap_deg < self.release_threshold_deg:
            self._pushed_since = None
        return self._pushed_since

    def _remember_target(self, t: float, target_rad: float) -> None:
        """Add a target, and forget those older than twice the delay.

        Keeping twice the delay, not just the delay, guarantees a target
        sent before t - delay_s is still remembered, to interpolate from.
        """
        self._target_times.append(t)
        self._target_angles_rad.append(target_rad)
        while self._target_times[0] < t - 2 * self.delay_s:
            self._target_times.popleft()
            self._target_angles_rad.popleft()

    def _target_at(self, t: float) -> float | None:
        """Return where the antenna was sent at t.

        Between two remembered targets, takes the point in between: the
        target sent at 1.03 s, between 11° at 1.02 s and 12° at 1.04 s, is
        11.5°. Returns None if t is before the oldest target remembered.
        """
        if t < self._target_times[0]:
            return None
        return float(np.interp(t, self._target_times, self._target_angles_rad))
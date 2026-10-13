"""Antenna pushes: someone pushing an antenna away from where it was sent."""

import logging
import math
from collections import deque

from reachy_alive.brain.sensory_cortex.touch.touch_frame import ANTENNA_SIDES, TouchFrame
from reachy_alive.shared_state import TouchFacts

logger = logging.getLogger(__name__)


class AntennaPush:
    """Follows one antenna: whether it is pushed away from where it was sent.

    The motor reaches each target late, by a delay that varies (stiff motor,
    jittery network). So the antenna is expected anywhere between the targets
    sent MIN_DELAY_S and MAX_DELAY_S earlier: the expected range. What counts
    is the gap outside that range; inside it, the gap is zero.

    A push starts when the gap reaches PUSH_THRESHOLD_DEG, and ends under
    RELEASE_THRESHOLD_DEG: two thresholds, so it doesn't flicker. A push in
    the direction the antenna already moves can hide in the range, up to
    about 5° while breathing.
    """

    PUSH_THRESHOLD_DEG = 5.0
    RELEASE_THRESHOLD_DEG = 3.0
    # How late the motor may run behind its target.
    MIN_DELAY_S = 0.05
    MAX_DELAY_S = 0.25

    def __init__(self) -> None:
        # The targets of the last moments, oldest first: when each was sent,
        # and where it sent the antenna.
        self._target_times: deque[float] = deque()
        self._target_positions_rad: deque[float] = deque()
        self._pushed_since: float | None = None

    def update(self, t: float, target_rad: float, measured_rad: float) -> float | None:
        """Read one sample of the antenna.

        Args:
            t: Time of the sample, in seconds, on a clock that only goes forward.
            target_rad: Where the antenna was just sent.
            measured_rad: Where the antenna is, measured.

        Returns:
            When the current push started, or None if the antenna isn't pushed.
        """
        self._add_target(t, target_rad)
        self._forget_targets_before(t - self.MAX_DELAY_S)
        expected_positions_rad = self._targets_sent_before(t - self.MIN_DELAY_S)
        if not expected_positions_rad:
            return self._pushed_since  # not enough history yet to judge

        gap_outside_expected_rad = max(
            min(expected_positions_rad) - measured_rad,  # below the expected range
            measured_rad - max(expected_positions_rad),  # above it
            0.0,  # inside it: the motor's lag explains everything
        )
        gap_outside_expected_deg = math.degrees(gap_outside_expected_rad)

        was_pushed = self._pushed_since is not None
        push_is_starting = not was_pushed and gap_outside_expected_deg >= self.PUSH_THRESHOLD_DEG
        push_is_ending = was_pushed and gap_outside_expected_deg < self.RELEASE_THRESHOLD_DEG
        if push_is_starting:
            self._pushed_since = t
        elif push_is_ending:
            self._pushed_since = None
        return self._pushed_since

    def _add_target(self, t: float, target_rad: float) -> None:
        """Remember where the antenna was sent at time t."""
        self._target_times.append(t)
        self._target_positions_rad.append(target_rad)

    def _forget_targets_before(self, oldest_worth_keeping: float) -> None:
        """Forget the targets sent before `oldest_worth_keeping`, in seconds."""
        while self._target_times[0] < oldest_worth_keeping:
            self._target_times.popleft()
            self._target_positions_rad.popleft()

    def _targets_sent_before(self, latest: float) -> list[float]:
        """Return the remembered target positions sent at or before `latest`, in radians."""
        return [
            position_rad
            for sent_time, position_rad in zip(self._target_times, self._target_positions_rad)
            if sent_time <= latest
        ]


class AntennaPushDetector:
    """Spots when someone pushes an antenna away from where it was sent.

    Follows each antenna with its own AntennaPush. While the robot moves
    itself, it stays quiet and forgets what it followed: an antenna pushed
    before the robot moved may no longer be.
    """

    def __init__(self, facts: TouchFacts) -> None:
        self._facts = facts
        self._pushes = self._fresh_pushes()

    def update(self, frame: TouchFrame) -> None:
        """Follow both antennas through one frame, and record whether each is pushed."""
        if frame.robot_moving_itself:
            self._forget_pushes()
            return
        for side, target_rad, measured_rad in zip(
            ANTENNA_SIDES, frame.targets_rad, frame.measured_rad
        ):
            was_pushed = self._facts.antenna_pushed_since(side) is not None
            pushed_since = self._pushes[side].update(frame.t, target_rad, measured_rad)
            self._facts.set_antenna_pushed_since(side, pushed_since)
            if pushed_since is not None and not was_pushed:
                logger.info("%s antenna pushed", side.capitalize())

    def _forget_pushes(self) -> None:
        self._pushes = self._fresh_pushes()
        for side in ANTENNA_SIDES:
            self._facts.set_antenna_pushed_since(side, None)

    @staticmethod
    def _fresh_pushes() -> dict[str, AntennaPush]:
        """One new AntennaPush per antenna, with no history."""
        return {side: AntennaPush() for side in ANTENNA_SIDES}

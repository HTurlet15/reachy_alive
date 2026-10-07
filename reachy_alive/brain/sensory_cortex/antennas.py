"""Touch felt through the antennas: someone pushing one away from where it was sent."""

import logging
import math
import threading
import time
from collections import deque

import numpy as np
from reachy_mini import ReachyMini

from reachy_alive.shared_state import SharedState

logger = logging.getLogger(__name__)

# The antennas in the SDK's order, on the real robot.
ANTENNA_SIDES = ("right", "left")


class AntennaPushDetector:
    """Spots when someone pushes one antenna away from where it was sent.

    The motor follows its target with a delay: an antenna sent to 10° at
    0.95 s only reaches 10° around 1.10 s. So at time t, the antenna isn't
    expected at the target just sent, but at the target sent `delay_s`
    earlier:

        time sent        0.95   1.00   1.05   1.10
        target           10°    11°    12°    13°
                          ↑
        at t = 1.10 s, with delay_s = 0.15, the antenna is expected at
        the target sent at 0.95 s: 10°, not 13°.

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
        delay_s: float = 0.15,
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


class AntennasSense:
    """Reads the antennas and records in SharedState when one is pushed.

    Runs in its own thread, never drives the robot. Each antenna's measured
    position is compared to where RobotController last sent it, by one
    AntennaPushDetector per antenna. It stays quiet while the robot moves
    itself (a move, waking up, going to sleep) and for a short while after:
    the targets then don't come from RobotController's poses, so it doesn't
    know where the antennas should be.

    Attributes:
        read_period_s: Time between two readings, in seconds.
        settle_after_move_s: How long it stays quiet after the robot last
            moved itself, in seconds.
    """

    def __init__(
        self,
        reachy_mini: ReachyMini,
        shared_state: SharedState,
        read_period_s: float = 0.01,
        settle_after_move_s: float = 0.5,
    ) -> None:
        """
        Args:
            reachy_mini: Connected robot instance, only read from.
            shared_state: Where pushes are recorded, and where the sense
                learns where the antennas were sent and whether the robot
                is moving itself.
            read_period_s: Time between two readings, in seconds.
            settle_after_move_s: How long it stays quiet after the robot
                last moved itself, in seconds.
        """
        self._reachy_mini = reachy_mini
        self._shared_state = shared_state
        self.read_period_s = read_period_s
        self.settle_after_move_s = settle_after_move_s
        self._push_detectors = self._fresh_push_detectors()
        self._last_seen_moving_at = -math.inf

    def run(self, stop_event: threading.Event) -> None:
        """Read the antennas until stop_event is set.

        Args:
            stop_event: Set externally to stop the sense.
        """
        while not stop_event.wait(self.read_period_s):
            self.read_once(time.monotonic())

    def read_once(self, now: float) -> None:
        """Take one reading of both antennas, and record whether each is pushed.

        Args:
            now: Time of the reading, in seconds, on time.monotonic()'s clock.
        """
        commanded_pose = self._shared_state.last_commanded_pose()
        if commanded_pose is None or self._robot_moves_itself(now):
            # New detectors: what the old ones remember (an antenna pushed
            # before the robot moved) may no longer be true.
            self._push_detectors = self._fresh_push_detectors()
            for side in ANTENNA_SIDES:
                self._shared_state.set_antenna_pushed_since(side, None)
            return

        present_rad = self._reachy_mini.get_present_antenna_joint_positions()
        for i, side in enumerate(ANTENNA_SIDES):
            was_pushed = self._shared_state.antenna_pushed_since(side) is not None
            pushed_since = self._push_detectors[side].update(
                now, commanded_pose.antennas[i], present_rad[i]
            )
            self._shared_state.set_antenna_pushed_since(side, pushed_since)
            if pushed_since is not None and not was_pushed:
                logger.info("%s antenna pushed", side.capitalize())

    def _robot_moves_itself(self, now: float) -> bool:
        """Whether the robot moves itself, or did so too recently for its targets to be gone."""
        if self._shared_state.is_move_playing():
            self._last_seen_moving_at = now
            return True
        return now - self._last_seen_moving_at < self.settle_after_move_s

    @staticmethod
    def _fresh_push_detectors() -> dict[str, AntennaPushDetector]:
        """One new push detector per antenna, with no history."""
        return {side: AntennaPushDetector() for side in ANTENNA_SIDES}
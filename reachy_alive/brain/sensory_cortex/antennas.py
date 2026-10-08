"""Touch felt through the antennas: someone pushing one away from where it was sent."""

import logging
import math
import threading
import time
from collections import deque

from reachy_mini import ReachyMini

from reachy_alive.shared_state import SharedState

logger = logging.getLogger(__name__)

# The antennas in the SDK's order, on the real robot.
ANTENNA_SIDES = ("right", "left")


class AntennaPushDetector:
    """Spots when someone pushes one antenna away from where it was sent.

    The motor reaches each target late, by a delay that varies (stiff motor,
    jittery network). So the antenna is expected anywhere between the
    targets sent `min_delay_s` and `max_delay_s` earlier: the expected
    range. What counts is the gap outside that range; inside it, the gap is
    zero.

    A push starts when the gap reaches `push_threshold_deg`, and ends under
    `release_threshold_deg`: two thresholds, so it doesn't flicker. A push in
    the direction the antenna already moves can hide in the range, up to
    about 5° while breathing.

    One detector watches one antenna.

    Attributes:
        push_threshold_deg: Gap outside the expected range at which a push
            starts, in degrees.
        release_threshold_deg: Gap outside the expected range under which a
            push ends, in degrees.
        min_delay_s: Shortest delay the motor may run behind its target, in
            seconds.
        max_delay_s: Longest delay the motor may run behind its target, in
            seconds.
    """

    def __init__(
        self,
        push_threshold_deg: float = 5.0,
        release_threshold_deg: float = 3.0,
        min_delay_s: float = 0.05,
        max_delay_s: float = 0.25,
    ) -> None:
        """
        Args:
            push_threshold_deg: Gap outside the expected range at which a
                push starts, in degrees.
            release_threshold_deg: Gap outside the expected range under which
                a push ends, in degrees.
            min_delay_s: Shortest delay the motor may run behind its target,
                in seconds.
            max_delay_s: Longest delay the motor may run behind its target,
                in seconds.
        """
        self.push_threshold_deg = push_threshold_deg
        self.release_threshold_deg = release_threshold_deg
        self.min_delay_s = min_delay_s
        self.max_delay_s = max_delay_s
        # The targets of the last moments, oldest first: when each was sent,
        # and where it sent the antenna.
        self._target_times: deque[float] = deque()
        self._target_positions_rad: deque[float] = deque()
        self._pushed_since: float | None = None

    def update(
        self, t: float, target_position_rad: float, measured_position_rad: float
    ) -> float | None:
        """Read one sample of the antenna.

        Args:
            t: Time of the sample, in seconds, on a clock that only goes
                forward.
            target_position_rad: Where the antenna was just sent.
            measured_position_rad: Where the antenna is, measured.

        Returns:
            When the current push started, or None if the antenna isn't
            pushed.
        """
        self._add_target(t, target_position_rad)
        self._forget_targets_before(t - self.max_delay_s)
        expected_positions_rad = self._targets_sent_before(t - self.min_delay_s)
        if not expected_positions_rad:
            return self._pushed_since  # not enough history yet to judge

        expected_low_rad = min(expected_positions_rad)
        expected_high_rad = max(expected_positions_rad)
        gap_outside_expected_rad = max(
            expected_low_rad - measured_position_rad,  # below the expected range
            measured_position_rad - expected_high_rad,  # above it
            0.0,  # inside it: the motor's lag explains everything
        )
        gap_outside_expected_deg = math.degrees(gap_outside_expected_rad)

        was_pushed = self._pushed_since is not None
        push_is_starting = not was_pushed and gap_outside_expected_deg >= self.push_threshold_deg
        push_is_ending = was_pushed and gap_outside_expected_deg < self.release_threshold_deg
        if push_is_starting:
            self._pushed_since = t
        elif push_is_ending:
            self._pushed_since = None
        return self._pushed_since

    def _add_target(self, t: float, target_position_rad: float) -> None:
        """Remember where the antenna was sent at time t."""
        self._target_times.append(t)
        self._target_positions_rad.append(target_position_rad)

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


class AntennasSense:
    """Reads the antennas and records in SharedState when one is pushed.

    Runs in its own thread, never drives the robot. Each antenna's measured
    position is compared to where RobotController sent it, by one
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
        if self._shared_state.is_move_playing():
            self._last_seen_moving_at = now
        robot_just_moved = now - self._last_seen_moving_at < self.settle_after_move_s
        commanded_pose = self._shared_state.last_commanded_pose()
        knows_where_antennas_should_be = commanded_pose is not None and not robot_just_moved

        if not knows_where_antennas_should_be:
            # New detectors: what the old ones remember (an antenna pushed
            # before the robot moved) may no longer be true.
            self._push_detectors = self._fresh_push_detectors()
            for side in ANTENNA_SIDES:
                self._shared_state.set_antenna_pushed_since(side, None)
            return

        measured_positions_rad = self._reachy_mini.get_present_antenna_joint_positions()
        for side, target_position_rad, measured_position_rad in zip(
            ANTENNA_SIDES, commanded_pose.antennas, measured_positions_rad
        ):
            was_pushed = self._shared_state.antenna_pushed_since(side) is not None
            pushed_since = self._push_detectors[side].update(
                now, target_position_rad, measured_position_rad
            )
            self._shared_state.set_antenna_pushed_since(side, pushed_since)

            is_pushed = pushed_since is not None
            push_just_started = is_pushed and not was_pushed
            if push_just_started:
                logger.info("%s antenna pushed", side.capitalize())

    @staticmethod
    def _fresh_push_detectors() -> dict[str, AntennaPushDetector]:
        """One new push detector per antenna, with no history."""
        return {side: AntennaPushDetector() for side in ANTENNA_SIDES}
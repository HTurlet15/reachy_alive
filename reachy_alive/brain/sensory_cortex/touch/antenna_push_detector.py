"""Antenna pushes: someone pushing an antenna away from where it was sent."""

import logging
import math
from collections import deque

from reachy_alive.brain.sensory_cortex.detector import Detector, SchmittTrigger
from reachy_alive.brain.sensory_cortex.touch.touch_features import ANTENNA_SIDES, TouchFeatures
from reachy_alive.shared_state import TouchFacts

logger = logging.getLogger(__name__)


class AntennaPushDetector(Detector):
    """Spots when someone pushes an antenna away from where it was sent.

    For each antenna, an ExpectedRange measures how far it stands outside
    where the motor's lag allows it to be, and a SchmittTrigger turns that
    gap into a push. While the robot moves itself, every push is forgotten.
    """

    # A push starts once the gap reaches the higher threshold, and ends under
    # the lower one, so it doesn't flicker.
    PUSH_THRESHOLD_DEG = 5.0
    RELEASE_THRESHOLD_DEG = 3.0
    # How late the motor may run behind its target.
    MIN_DELAY_S = 0.05
    MAX_DELAY_S = 0.25

    def __init__(self, facts: TouchFacts) -> None:
        """Start following both antennas, with nothing remembered yet."""
        super().__init__(facts)
        self._start_afresh()

    def _start_afresh(self) -> None:
        """Follow both antennas from scratch: no target remembered, no push going on."""
        self._expected_ranges = {
            side: ExpectedRange(min_delay_s=self.MIN_DELAY_S, max_delay_s=self.MAX_DELAY_S)
            for side in ANTENNA_SIDES
        }
        self._push_triggers = {
            side: SchmittTrigger(
                on_threshold=self.PUSH_THRESHOLD_DEG, off_threshold=self.RELEASE_THRESHOLD_DEG
            )
            for side in ANTENNA_SIDES
        }

    def _detect(self, features: TouchFeatures) -> None:
        """Follow both antennas through one reading, and record whether each is pushed."""
        for side, target_rad, measured_rad in zip(
            ANTENNA_SIDES, features.targets_rad, features.measured_rad, strict=True
        ):
            expected_range = self._expected_ranges[side]
            push_trigger = self._push_triggers[side]

            expected_range.remember_target(features.perceived_at, target_rad)
            gap_deg = expected_range.gap_outside_deg(features.perceived_at, measured_rad)
            push_starts = push_trigger.would_turn_on(gap_deg)
            push_trigger.update(features.perceived_at, gap_deg)

            self._facts.record_antenna_pushed_since(side, push_trigger.on_since)
            if push_starts:
                logger.info("%s antenna pushed", side.capitalize())

    def _while_robot_moves(self, features: TouchFeatures) -> None:
        """Forget every push: an antenna pushed before the robot moved may no longer be."""
        self._start_afresh()
        for side in ANTENNA_SIDES:
            self._facts.record_antenna_pushed_since(side, None)


class ExpectedRange:
    """Where an antenna may be, given the targets it was sent: the motor runs late.

    The motor reaches each target late, by a delay that varies (stiff motor,
    jittery network). So the antenna is expected anywhere between the targets
    sent min_delay_s and max_delay_s earlier. What counts is the gap outside
    that range: inside it, the motor's lag explains everything. A push in the
    direction the antenna already moves can hide in the range, up to about 5°
    while breathing.
    """

    def __init__(self, min_delay_s: float, max_delay_s: float) -> None:
        """Set how late the motor may run behind its target.

        Args:
            min_delay_s: The shortest delay, in seconds.
            max_delay_s: The longest delay, in seconds.
        """
        self._min_delay_s = min_delay_s
        self._max_delay_s = max_delay_s
        # The targets of the last moments, oldest first, as (sent_at,
        # position_rad): when each was sent, and where it sent the antenna.
        self._sent_targets: deque[tuple[float, float]] = deque()

    def remember_target(self, t: float, target_rad: float) -> None:
        """Remember where the antenna was sent at t, and forget the targets too old to matter.

        Args:
            t: When it was sent, in seconds, on a monotonic clock.
            target_rad: Where it was sent.
        """
        self._sent_targets.append((t, target_rad))
        oldest_sent_at, _ = self._sent_targets[0]
        while oldest_sent_at < t - self._max_delay_s:
            self._sent_targets.popleft()
            oldest_sent_at, _ = self._sent_targets[0]

    def gap_outside_deg(self, t: float, measured_rad: float) -> float:
        """Return how far outside the expected range the antenna is at t, in degrees.

        It is 0 inside the range, and 0 until a target was sent long enough ago
        to judge.

        Args:
            t: When the antenna was measured, in seconds, on a monotonic clock.
            measured_rad: Where it was measured.
        """
        expected_positions_rad = [
            position_rad
            for sent_at, position_rad in self._sent_targets
            if sent_at <= t - self._min_delay_s
        ]
        if not expected_positions_rad:
            return 0.0  # nothing sent long enough ago to judge yet
        gap_rad = max(
            min(expected_positions_rad) - measured_rad,  # below the expected range
            measured_rad - max(expected_positions_rad),  # above it
            0.0,  # inside it
        )
        return math.degrees(gap_rad)

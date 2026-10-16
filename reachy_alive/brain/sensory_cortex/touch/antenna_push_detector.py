"""Antenna pushes: someone pushing an antenna away from where it was sent."""

import logging
import math
from collections import deque

from reachy_alive.brain.sensory_cortex.detector import Detector, SchmittTrigger
from reachy_alive.brain.sensory_cortex.touch.touch_features import ANTENNA_SIDES, TouchFeatures
from reachy_alive.shared_state import TouchFacts

logger = logging.getLogger(__name__)


class AntennaPush:
    """Follows one antenna: whether it is pushed away from where it was sent.

    The motor reaches each target late, by a delay that varies (stiff motor,
    jittery network). So the antenna is expected anywhere between the targets
    sent MIN_DELAY_S and MAX_DELAY_S earlier: the expected range. What counts
    is the gap outside that range; inside it, the gap is zero.

    A push starts when the gap reaches PUSH_THRESHOLD_DEG, and ends under
    RELEASE_THRESHOLD_DEG: a SchmittTrigger, so it doesn't flicker. A push in
    the direction the antenna already moves can hide in the range, up to
    about 5° while breathing.
    """

    PUSH_THRESHOLD_DEG = 5.0
    RELEASE_THRESHOLD_DEG = 3.0
    # How late the motor may run behind its target.
    MIN_DELAY_S = 0.05
    MAX_DELAY_S = 0.25

    def __init__(self) -> None:
        # The targets of the last moments, oldest first, as (sent_at,
        # position_rad): when each was sent, and where it sent the antenna.
        self._sent_targets: deque[tuple[float, float]] = deque()
        self._push_trigger = SchmittTrigger(
            on_threshold=self.PUSH_THRESHOLD_DEG, off_threshold=self.RELEASE_THRESHOLD_DEG
        )

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
            return self._push_trigger.on_since  # not enough history yet to judge

        gap_outside_expected_rad = max(
            min(expected_positions_rad) - measured_rad,  # below the expected range
            measured_rad - max(expected_positions_rad),  # above it
            0.0,  # inside it: the motor's lag explains everything
        )
        gap_outside_expected_deg = math.degrees(gap_outside_expected_rad)

        self._push_trigger.update(t, gap_outside_expected_deg)
        return self._push_trigger.on_since

    def _add_target(self, t: float, target_rad: float) -> None:
        """Remember where the antenna was sent at time t."""
        self._sent_targets.append((t, target_rad))

    def _forget_targets_before(self, oldest_worth_keeping: float) -> None:
        """Forget the targets sent before `oldest_worth_keeping`, in seconds."""
        oldest_sent_at, _ = self._sent_targets[0]
        while oldest_sent_at < oldest_worth_keeping:
            self._sent_targets.popleft()
            oldest_sent_at, _ = self._sent_targets[0]

    def _targets_sent_before(self, latest: float) -> list[float]:
        """Return the remembered target positions sent at or before `latest`, in radians."""
        return [
                position_rad 
                for sent_at, position_rad in self._sent_targets 
                if sent_at <= latest
                ]


class AntennaPushDetector(Detector):
    """Spots when someone pushes an antenna away from where it was sent.

    Follows each antenna with its own AntennaPush, and forgets them while
    the robot moves itself.
    """

    def __init__(self, facts: TouchFacts) -> None:
        super().__init__(facts)
        self._pushes = self._fresh_pushes()

    def _detect(self, features: TouchFeatures) -> None:
        """Follow both antennas through one reading, and record whether each is pushed."""
        for side, target_rad, measured_rad in zip(
            ANTENNA_SIDES, features.targets_rad, features.measured_rad
        ):
            was_pushed = self._facts.antenna_pushed_since(side) is not None
            pushed_since = self._pushes[side].update(features.t, target_rad, measured_rad)
            self._facts.set_antenna_pushed_since(side, pushed_since)
            if pushed_since is not None and not was_pushed:
                logger.info("%s antenna pushed", side.capitalize())

    def _while_robot_moves(self, features: TouchFeatures) -> None:
        """Forget every push: an antenna pushed before the robot moved may no longer be."""
        self._pushes = self._fresh_pushes()
        for side in ANTENNA_SIDES:
            self._facts.set_antenna_pushed_since(side, None)

    @staticmethod
    def _fresh_pushes() -> dict[str, AntennaPush]:
        """One new AntennaPush per antenna, with no history."""
        return {side: AntennaPush() for side in ANTENNA_SIDES}
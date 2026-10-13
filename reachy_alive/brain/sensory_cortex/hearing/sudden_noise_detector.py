"""Sudden noises: a loud sound nobody expected, like a clap or a door slamming."""

import logging
import math

from reachy_alive.brain.sensory_cortex.hearing.hearing_frame import HearingFrame
from reachy_alive.shared_state import HearingFacts

logger = logging.getLogger(__name__)


class SuddenNoiseDetector:
    """Spots sudden noises in the loudness of the sound: loud sounds nobody expected.

    A loud sound jumps well above the background, the level of the last few
    seconds, and goes on until it fades. It is expected when another one
    started moments ago and it isn't much louder: of three claps in a row,
    only the first is a sudden noise.

    The robot hears its own moves: it keeps listening to them, so the
    background follows, but records no noise starting then.
    """

    # The background trails the sound like a capacitor charging through a
    # resistor: after one time constant, it has covered 63% of the way.
    BACKGROUND_TIME_CONSTANT_S = 2.0

    # A loud sound starts above the higher threshold and ends under the lower
    # one, so a lasting sound, like a vacuum cleaner, counts once. The start
    # of a sentence jumps about 26 dB: measured on the robot.
    START_THRESHOLD_DB = 30.0
    END_THRESHOLD_DB = 10.0

    # A loud sound stays expected this long after the last one, unless it is
    # much louder.
    HABITUATION_S = 10.0
    MUCH_LOUDER_DB = 10.0

    def __init__(self, facts: HearingFacts) -> None:
        self._facts = facts
        # Times below are on the sound's own clock: frame.time_listened_s.
        self._background_dbfs: float | None = None
        self._background_updated_at = -math.inf
        self._hearing_a_loud_sound = False
        self._last_loud_sound_at = -math.inf
        self._last_loud_sound_height_db = -math.inf

    def update(self, frame: HearingFrame) -> None:
        """Read one stretch of sound, and record a sudden noise if one starts on it."""
        noise_starts = self._noise_starts(frame.time_listened_s, frame.level_dbfs)
        if noise_starts and not frame.robot_moving_itself:
            self._facts.record_sudden_noise(frame.t)
            logger.info("Sudden noise")

    def _noise_starts(self, time_listened_s: float, level_dbfs: float) -> bool:
        """Follow the sound through one stretch; return whether a sudden noise starts on it."""
        if self._background_dbfs is None:
            self._start_background(time_listened_s, level_dbfs)
            return False

        # Measured before the background moves, so a sound doesn't shrink its own jump.
        height_above_background_db = level_dbfs - self._background_dbfs
        self._follow_background(time_listened_s, level_dbfs)

        loud_sound_starts = self._is_loud_sound_starting(height_above_background_db)
        self._track_loud_sound(height_above_background_db)
        if not loud_sound_starts:
            return False

        is_expected = self._expects(time_listened_s, height_above_background_db)
        self._remember_loud_sound(time_listened_s, height_above_background_db)
        return not is_expected

    def _start_background(self, time_listened_s: float, level_dbfs: float) -> None:
        """Take the first level heard as the background."""
        self._background_dbfs = level_dbfs
        self._background_updated_at = time_listened_s

    def _follow_background(self, time_listened_s: float, level_dbfs: float) -> None:
        """Move the background a step toward the level just heard."""
        elapsed_s = time_listened_s - self._background_updated_at
        self._background_updated_at = time_listened_s
        smoothing_factor = 1.0 - math.exp(-elapsed_s / self.BACKGROUND_TIME_CONSTANT_S)
        self._background_dbfs += smoothing_factor * (level_dbfs - self._background_dbfs)

    def _is_loud_sound_starting(self, height_above_background_db: float) -> bool:
        """Whether a new loud sound starts: none is going on, and the sound jumps high enough."""
        jumps_high_enough = height_above_background_db >= self.START_THRESHOLD_DB
        return not self._hearing_a_loud_sound and jumps_high_enough

    def _track_loud_sound(self, height_above_background_db: float) -> None:
        """Note whether a loud sound is going on, from its start until it fades."""
        if self._hearing_a_loud_sound:
            has_faded = height_above_background_db < self.END_THRESHOLD_DB
            self._hearing_a_loud_sound = not has_faded
        else:
            self._hearing_a_loud_sound = self._is_loud_sound_starting(height_above_background_db)

    def _expects(self, time_listened_s: float, height_above_background_db: float) -> bool:
        """Whether a loud sound starting now is expected: like one heard moments ago."""
        heard_one_moments_ago = time_listened_s - self._last_loud_sound_at < self.HABITUATION_S
        much_louder = (
            height_above_background_db >= self._last_loud_sound_height_db + self.MUCH_LOUDER_DB
        )
        return heard_one_moments_ago and not much_louder

    def _remember_loud_sound(
        self, time_listened_s: float, height_above_background_db: float
    ) -> None:
        """Keep the last loud sound in mind, expected or not: each one keeps us used to them."""
        self._last_loud_sound_at = time_listened_s
        self._last_loud_sound_height_db = height_above_background_db

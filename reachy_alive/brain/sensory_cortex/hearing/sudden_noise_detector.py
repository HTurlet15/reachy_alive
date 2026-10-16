"""Sudden noises: a loud sound nobody expected, like a clap or a door slamming."""

import logging
import math

from reachy_alive.brain.sensory_cortex.detector import Detector, SchmittTrigger
from reachy_alive.brain.sensory_cortex.hearing.hearing_features import HearingFeatures
from reachy_alive.shared_state import HearingFacts

logger = logging.getLogger(__name__)


class SuddenNoiseDetector(Detector):
    """Spots sudden noises in the loudness of the sound: loud sounds nobody expected.

    A loud sound jumps well above the background, the level of the last few
    seconds, and goes on until it fades. It is expected when another one
    started moments ago and it isn't much louder: of three claps in a row,
    only the first is a sudden noise.

    The robot hears its own moves: it keeps following the sound then, but
    records no noise.
    """

    # The background trails the sound like a capacitor charging through a
    # resistor: after one time constant, it has covered 63% of the way.
    BACKGROUND_TIME_CONSTANT_S = 2.0

    # A loud sound starts above the higher threshold and ends under the lower
    # one, through a SchmittTrigger: a lasting sound, like a vacuum cleaner,
    # counts once. The start of a sentence jumps about 26 dB: measured on the
    # robot.
    START_THRESHOLD_DB = 30.0
    END_THRESHOLD_DB = 10.0

    # A loud sound stays expected this long after the last one, unless it is
    # much louder.
    HABITUATION_S = 10.0
    MUCH_LOUDER_DB = 10.0

    def __init__(self, facts: HearingFacts) -> None:
        super().__init__(facts)
        # Times below are on the sound's own clock: features.time_listened_s.
        self._background_dbfs: float | None = None
        self._background_updated_at = -math.inf
        self._loud_sound_trigger = SchmittTrigger(
            on_threshold=self.START_THRESHOLD_DB, off_threshold=self.END_THRESHOLD_DB
        )
        self._last_loud_sound_at = -math.inf
        self._last_loud_sound_height_db = -math.inf

    def _detect(self, features: HearingFeatures) -> None:
        """Follow the sound through one stretch, and record a sudden noise if one starts on it."""
        # Asked before following the sound, which updates everything the
        # question compares with: the background, and the last loud sound.
        noise_starts = self._is_sudden_noise(features)
        self._follow_sound(features)
        if noise_starts:
            self._facts.record_sudden_noise(features.t)
            logger.info("Sudden noise")

    def _while_robot_moves(self, features: HearingFeatures) -> None:
        """Follow the sound through one stretch, without asking about noises: they are the robot's.

        The background and the habituation stay up to date for when the move is over.
        """
        self._follow_sound(features)

    def _is_sudden_noise(self, features: HearingFeatures) -> bool:
        """Whether a sudden noise starts on this stretch: a loud sound nobody expected."""
        if self._background_dbfs is None:
            return False  # nothing heard yet to compare with
        height_db = self._height_above_background_db(features.level_dbfs)
        loud_sound_starts = self._loud_sound_trigger.would_turn_on(height_db)
        is_expected = self._expects(features.time_listened_s, height_db)
        return loud_sound_starts and not is_expected

    def _follow_sound(self, features: HearingFeatures) -> None:
        """Update the background, the loud sound going on, and the last loud sound heard."""
        if self._background_dbfs is None:
            self._start_background(features.time_listened_s, features.level_dbfs)
            return
        # Measured before the background moves, so a sound doesn't shrink its own jump.
        height_db = self._height_above_background_db(features.level_dbfs)
        loud_sound_starts = self._loud_sound_trigger.would_turn_on(height_db)
        self._follow_background(features.time_listened_s, features.level_dbfs)
        self._loud_sound_trigger.update(features.time_listened_s, height_db)
        if loud_sound_starts:
            self._remember_loud_sound(features.time_listened_s, height_db)

    def _height_above_background_db(self, level_dbfs: float) -> float:
        """How far a level stands above the background, in dB."""
        return level_dbfs - self._background_dbfs

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
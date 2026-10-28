"""Sudden noises: a loud sound nobody expected, like a clap or a door slamming."""

import logging
import math

from reachy_alive.brain.sensory_cortex.detector import Background, Detector, SchmittTrigger
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
    records no noise, and doesn't get used to its own sounds.
    """

    # Short enough for the background to follow a room that gets louder,
    # long enough for a clap to stand out from it.
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
        """Build the detector's mechanisms, from its settings."""
        super().__init__(facts)
        self._start_afresh()

    def forget(self) -> None:
        """Forget the room: its background, the loud sound going on, the habit.

        The room may have changed while the sense was off. The last sudden
        noise stays: it still happened.
        """
        self._start_afresh()

    def _start_afresh(self) -> None:
        """Listen from scratch: no background, no loud sound going on, no habit."""
        # Every mechanism below follows the sound's own clock: features.time_listened_s.
        self._background = Background(time_constant_s=self.BACKGROUND_TIME_CONSTANT_S)
        self._loud_sound_trigger = SchmittTrigger(
            on_threshold=self.START_THRESHOLD_DB, off_threshold=self.END_THRESHOLD_DB
        )
        self._habituation = Habituation(
            lasts_s=self.HABITUATION_S, much_louder_db=self.MUCH_LOUDER_DB
        )

    def _detect(self, features: HearingFeatures) -> None:
        """Follow the sound through one frame, and record a sudden noise if one starts on it."""
        # Judged before the sound is followed and remembered, since both move what it
        # is judged against: the background (a sound would shrink its own jump), the
        # loud sound going on, and the habituation.
        height_db = self._background.height_of(features.level_dbfs)
        loud_sound_starts = self._loud_sound_trigger.would_turn_on(height_db)
        is_expected = self._habituation.is_expected(features.time_listened_s, height_db)
        self._follow_sound(features, height_db)
        if loud_sound_starts:
            self._habituation.remember(features.time_listened_s, height_db)
        if loud_sound_starts and not is_expected:
            self._facts.record_sudden_noise(features.perceived_at)
            logger.info("Sudden noise")

    def _while_robot_moves(self, features: HearingFeatures) -> None:
        """Follow the sound through one frame, without judging it: it is the robot's.

        The background and the loud sound going on stay up to date for when
        the move is over. The habituation doesn't remember the robot's own
        sounds: they say nothing about what to expect from the room.
        """
        height_db = self._background.height_of(features.level_dbfs)
        self._follow_sound(features, height_db)

    def _follow_sound(self, features: HearingFeatures, height_db: float) -> None:
        """Update the background and the loud sound going on."""
        self._background.follow(features.time_listened_s, features.level_dbfs)
        self._loud_sound_trigger.update(features.time_listened_s, height_db)


class Habituation:
    """Gets used to loud sounds: one is expected for a while after another, unless much louder.

    Every loud sound is remembered, even an expected one: a sound that keeps
    repeating stays expected, and only the first of three claps in a row is a
    surprise.
    """

    def __init__(self, lasts_s: float, much_louder_db: float) -> None:
        """Set how long the habit lasts, and what breaks it.

        Args:
            lasts_s: How long a loud sound stays expected after the last one.
            much_louder_db: How much louder than the last one a sound must be
                to surprise anyway.
        """
        self._lasts_s = lasts_s
        self._much_louder_db = much_louder_db
        self._last_loud_sound_at = -math.inf
        self._last_loud_sound_height_db = -math.inf

    def is_expected(self, t: float, height_db: float) -> bool:
        """Return whether a loud sound starting at t is expected: like one heard moments ago.

        Args:
            t: When the sound starts, in seconds, on a monotonic clock.
            height_db: How far it stands above the background.
        """
        heard_one_moments_ago = t - self._last_loud_sound_at < self._lasts_s
        much_louder = height_db >= self._last_loud_sound_height_db + self._much_louder_db
        return heard_one_moments_ago and not much_louder

    def remember(self, t: float, height_db: float) -> None:
        """Keep a loud sound in mind, expected or not."""
        self._last_loud_sound_at = t
        self._last_loud_sound_height_db = height_db

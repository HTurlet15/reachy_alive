"""Hearing: a sudden noise, like a clap or a door slamming.

The microphones give 16,000 samples per second, each between -1 and 1. Sound
is judged 20 ms at a time: each stretch of 320 samples becomes one loudness
level.
"""

import logging
import math
import threading
import time

import numpy as np
from reachy_mini import ReachyMini

from reachy_alive.shared_state import SharedState

logger = logging.getLogger(__name__)

# Given to silence: a level in decibels has no value at zero.
SILENCE_DBFS = -100.0


def loudness_dbfs(samples: np.ndarray) -> float:
    """Return how loud a stretch of sound is, in dBFS.

    0 dBFS is the loudest sound the microphones can report. Every -6 dB
    halves the sound.

    Args:
        samples: Sound samples between -1 and 1, any shape.
    """
    if samples.size == 0:
        return SILENCE_DBFS
    # The samples swing around 0: their root mean square says how far.
    mean_square = float(np.mean(np.square(samples)))
    root_mean_square = math.sqrt(mean_square)
    if root_mean_square == 0.0:
        return SILENCE_DBFS
    level_dbfs = 20 * math.log10(root_mean_square)
    return max(level_dbfs, SILENCE_DBFS)


class SuddenNoiseDetector:
    """Spots sudden noises in a stream of loudness levels: loud sounds nobody expected.

    A loud sound jumps well above the background, the level of the last few
    seconds, and goes on until it fades. It is expected when another one
    started moments ago and it isn't much louder: of three claps in a row,
    only the first is a sudden noise.
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

    def __init__(self) -> None:
        self._background_dbfs: float | None = None
        self._background_updated_at = -math.inf
        self._hearing_a_loud_sound = False
        self._last_loud_sound_at = -math.inf
        self._last_loud_sound_height_db = -math.inf

    def update(self, t: float, level_dbfs: float) -> bool:
        """Read the loudness of one stretch of sound.

        Args:
            t: Time of the stretch, in seconds, on a clock that only goes
                forward.
            level_dbfs: How loud the stretch is.

        Returns:
            True if a sudden noise starts on this stretch.
        """
        if self._background_dbfs is None:
            self._start_background(t, level_dbfs)
            return False

        # Measured before the background moves, so a sound doesn't shrink its own jump.
        height_above_background_db = level_dbfs - self._background_dbfs
        self._follow_background(t, level_dbfs)

        loud_sound_starts = self._is_loud_sound_starting(height_above_background_db)
        self._track_loud_sound(height_above_background_db)
        if not loud_sound_starts:
            return False

        is_expected = self._expects(t, height_above_background_db)
        self._remember_loud_sound(t, height_above_background_db)
        return not is_expected

    def _start_background(self, t: float, level_dbfs: float) -> None:
        """Take the first level heard as the background."""
        self._background_dbfs = level_dbfs
        self._background_updated_at = t

    def _follow_background(self, t: float, level_dbfs: float) -> None:
        """Move the background a step toward the level just heard."""
        elapsed_s = t - self._background_updated_at
        self._background_updated_at = t
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

    def _expects(self, t: float, height_above_background_db: float) -> bool:
        """Whether a loud sound starting now is expected: like one heard moments ago."""
        heard_one_moments_ago = t - self._last_loud_sound_at < self.HABITUATION_S
        much_louder = (
            height_above_background_db >= self._last_loud_sound_height_db + self.MUCH_LOUDER_DB
        )
        return heard_one_moments_ago and not much_louder

    def _remember_loud_sound(self, t: float, height_above_background_db: float) -> None:
        """Keep the last loud sound in mind, expected or not: each one keeps us used to them."""
        self._last_loud_sound_at = t
        self._last_loud_sound_height_db = height_above_background_db


class HearingSense:
    """Listens to the microphones and records sudden noises in SharedState.

    Runs in its own thread and never drives the robot. Sound arrives in
    chunks of any length: the sense cuts it into stretches, and times them by
    how much sound it has heard. The robot hears its own moves too, so noises
    starting while it moves itself, or right after, aren't recorded.
    """

    STRETCH_S = 0.02
    # How long noises are still ignored after the robot last moved itself.
    SETTLE_AFTER_MOVE_S = 0.5

    def __init__(
        self,
        reachy_mini: ReachyMini,
        shared_state: SharedState,
        sudden_noise_detector: SuddenNoiseDetector | None = None,
    ) -> None:
        """Size the stretches from the microphones' sample rate.

        Args:
            reachy_mini: Connected robot instance, only listened to.
            shared_state: Where sudden noises are recorded, and where the
                sense learns whether the robot is moving itself.
            sudden_noise_detector: Spots sudden noises in the loudness levels.
        """
        self._reachy_mini = reachy_mini
        self._shared_state = shared_state
        self._sudden_noise_detector = sudden_noise_detector or SuddenNoiseDetector()
        sample_rate_hz = reachy_mini.media.get_input_audio_samplerate()
        self._has_microphones = sample_rate_hz > 0
        self._samples_per_stretch = round(sample_rate_hz * self.STRETCH_S)
        self._samples_not_judged_yet = np.zeros(0)
        # The detector's clock: chunks can arrive late, the sound itself can't.
        self._sound_heard_s = 0.0
        self._last_seen_moving_at = -math.inf

    def run(self, stop_event: threading.Event) -> None:
        """Listen until stop_event is set.

        Args:
            stop_event: Set externally to stop the sense.
        """
        if not self._has_microphones:
            logger.info("No microphones: sudden noises won't be heard")
            return
        self._reachy_mini.media.start_recording()
        try:
            while not stop_event.is_set():
                self.read_once(time.monotonic())  # waits up to 20 ms for sound
        finally:
            self._reachy_mini.media.stop_recording()

    def read_once(self, now: float) -> None:
        """Judge the next chunk of sound, and record a sudden noise if it holds one.

        Args:
            now: Time of the reading, in seconds, on time.monotonic()'s clock.
        """
        chunk = self._reachy_mini.media.get_audio_sample()
        if chunk is None:
            return  # no new sound yet

        self._watch_for_own_moves(now)
        robot_may_hear_itself = now - self._last_seen_moving_at < self.SETTLE_AFTER_MOVE_S

        for stretch in self._take_full_stretches(chunk):
            self._sound_heard_s += self.STRETCH_S
            noise_starts = self._sudden_noise_detector.update(
                self._sound_heard_s, loudness_dbfs(stretch)
            )
            if noise_starts and not robot_may_hear_itself:
                self._shared_state.record_sudden_noise(now)
                logger.info("Sudden noise")

    def _watch_for_own_moves(self, now: float) -> None:
        """Note when the robot was last seen moving itself."""
        if self._shared_state.is_move_playing():
            self._last_seen_moving_at = now

    def _take_full_stretches(self, chunk: np.ndarray) -> list[np.ndarray]:
        """Add a chunk to the samples not judged yet, and take out every full stretch."""
        # Loudness doesn't need stereo: the two microphones are averaged.
        mono_samples = chunk.mean(axis=1) if chunk.ndim == 2 else chunk
        self._samples_not_judged_yet = np.concatenate([self._samples_not_judged_yet, mono_samples])

        stretches = []
        while len(self._samples_not_judged_yet) >= self._samples_per_stretch:
            stretches.append(self._samples_not_judged_yet[: self._samples_per_stretch])
            self._samples_not_judged_yet = self._samples_not_judged_yet[self._samples_per_stretch :]
        return stretches
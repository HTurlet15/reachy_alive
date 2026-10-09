"""Hearing: a sudden noise, like a clap or a door slamming.

The microphones give sound as samples: 16,000 numbers per second, each
between -1 and 1, the position of the membrane at that instant. Sound is
judged 20 ms at a time: each stretch of 320 samples becomes one loudness
level, and the levels go to the detector.
"""

import math

import numpy as np

# The loudness given to silence, in dBFS: a level in decibels has no value at zero.
SILENCE_DBFS = -100.0


def loudness_dbfs(samples: np.ndarray) -> float:
    """Return how loud a stretch of sound is, in dBFS.

    dBFS (decibels relative to full scale): 0 is the loudest sound the
    microphones can report, quieter sounds are negative. Every -6 dB halves
    the sound: -6 dBFS is half the loudest, -12 a quarter.

    Args:
        samples: Sound samples between -1 and 1, any shape.
    """
    if samples.size == 0:
        return SILENCE_DBFS
    # The samples swing around 0, so their plain average says nothing.
    # Their root mean square does: how far, typically, they swing.
    mean_square = float(np.mean(np.square(samples)))
    root_mean_square = math.sqrt(mean_square)
    if root_mean_square == 0.0:
        return SILENCE_DBFS
    level_dbfs = 20 * math.log10(root_mean_square)
    return max(level_dbfs, SILENCE_DBFS)


class SuddenNoiseDetector:
    """Spots sudden noises in a stream of loudness levels.

    The room's level drifts (the microphones adjust their own gain), so a
    noise is judged against the background heard over the last seconds,
    not against a fixed level. The background follows the sound slowly: a
    clap barely moves it, a sound rising over seconds pulls it along.

    A sudden noise starts when the sound jumps `start_threshold_db` above
    the background, and ends once it is less than `end_threshold_db` above
    it: two thresholds, so a noise that lasts, like a vacuum cleaner
    switched on, is reported once while the background catches up.

    Attributes:
        start_threshold_db: Jump above the background at which a noise
            starts, in dB.
        end_threshold_db: Height above the background under which it has
            ended, in dB.
        background_time_constant_s: How slowly the background follows the
            sound, in seconds.
    """

    def __init__(
        self,
        start_threshold_db: float = 25.0,
        end_threshold_db: float = 10.0,
        background_time_constant_s: float = 2.0,
    ) -> None:
        """
        Args:
            start_threshold_db: Jump above the background at which a noise
                starts, in dB.
            end_threshold_db: Height above the background under which it has
                ended, in dB.
            background_time_constant_s: How slowly the background follows
                the sound, in seconds.
        """
        self.start_threshold_db = start_threshold_db
        self.end_threshold_db = end_threshold_db
        self.background_time_constant_s = background_time_constant_s
        self._background_dbfs: float | None = None
        self._background_updated_at = -math.inf
        self._in_noise = False

    def update(self, t: float, level_dbfs: float) -> bool:
        """Read the loudness of one stretch of sound.

        Args:
            t: Time of the stretch, in seconds, on a clock that only goes
                forward.
            level_dbfs: How loud the stretch is, in dBFS.

        Returns:
            True if this stretch starts a new sudden noise.
        """
        if self._background_dbfs is None:
            self._background_dbfs = level_dbfs  # the first level sets the background
            self._background_updated_at = t
            return False

        # Measured before the background moves, so a noise doesn't shrink its own jump.
        height_above_background_db = level_dbfs - self._background_dbfs
        self._follow_background(t, level_dbfs)

        noise_is_starting = (
            not self._in_noise and height_above_background_db >= self.start_threshold_db
        )
        noise_is_ending = self._in_noise and height_above_background_db < self.end_threshold_db
        if noise_is_starting:
            self._in_noise = True
        elif noise_is_ending:
            self._in_noise = False
        return noise_is_starting

    def _follow_background(self, t: float, level_dbfs: float) -> None:
        """Move the background a step toward the level just heard.

        Like a capacitor charging through a resistor: the step grows with
        the time since the last one, and after one time constant of steady
        sound, the background has covered about 63% of the way to it.
        """
        elapsed_s = t - self._background_updated_at
        self._background_updated_at = t
        smoothing_factor = 1.0 - math.exp(-elapsed_s / self.background_time_constant_s)
        self._background_dbfs += smoothing_factor * (level_dbfs - self._background_dbfs)
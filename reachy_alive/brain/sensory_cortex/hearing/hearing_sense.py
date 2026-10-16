"""The hearing sense: how loud the sound is, 20 ms at a time.

The microphones give 16,000 samples per second, each between -1 and 1. Each
stretch of 320 samples becomes one loudness level.
"""

import math

import numpy as np
from reachy_mini import ReachyMini

from reachy_alive.brain.sensory_cortex.hearing.hearing_features import HearingFeatures
from reachy_alive.brain.sensory_cortex.sense import Sense
from reachy_alive.shared_state import SharedState

# Given to silence: a level in decibels has no value at zero.
SILENCE_DBFS = -100.0


class HearingSense(Sense):
    """Listens to the microphones and describes each stretch of sound by its HearingFeatures.

    Sound arrives in chunks of any length: the sense cuts it into stretches,
    and times them by how long it has listened.
    """

    # Waiting for the next chunk paces the sense; this floor stops it spinning when the
    # microphones give nothing at once, and still drains a backlog at 200 stretches a second.
    PERIOD_S = 0.005
    STRETCH_S = 0.02

    def __init__(self, reachy_mini: ReachyMini, shared_state: SharedState) -> None:
        """Size the stretches from the microphones' sample rate.

        Args:
            reachy_mini: Connected robot instance, only listened to.
            shared_state: Where the sense learns whether the robot is moving itself.
        """
        super().__init__(reachy_mini, shared_state)
        self._sample_rate_hz = reachy_mini.media.get_input_audio_samplerate()
        self._samples_per_stretch = round(self._sample_rate_hz * self.STRETCH_S)
        self._samples_not_read_yet = np.zeros(0)
        # The sound's own clock, never reset: chunks can arrive late, the sound itself can't.
        self._time_listened_s = 0.0

    def is_available(self) -> bool:
        """Return whether the robot has microphones: without any, the sample rate isn't positive."""
        return self._sample_rate_hz > 0

    def open(self) -> None:
        """Start recording."""
        self._reachy_mini.media.start_recording()

    def _perceive(self, perceived_at: float, robot_moving_itself: bool) -> HearingFeatures | None:
        """Describe the next stretch of sound, or return None if no full stretch came yet."""
        if not self._has_full_stretch():
            self._add_next_chunk()
        if not self._has_full_stretch():
            return None  # not enough sound yet

        stretch = self._take_stretch()
        self._time_listened_s += self.STRETCH_S
        return HearingFeatures(
            perceived_at=perceived_at,
            time_listened_s=self._time_listened_s,
            level_dbfs=self.loudness_dbfs(stretch),
            robot_moving_itself=robot_moving_itself,
        )

    def close(self) -> None:
        """Stop recording."""
        self._reachy_mini.media.stop_recording()

    def _has_full_stretch(self) -> bool:
        """Return whether the samples not read yet hold a full stretch."""
        return len(self._samples_not_read_yet) >= self._samples_per_stretch

    def _add_next_chunk(self) -> None:
        """Add the microphones' next chunk of sound, if any, to the samples not read yet."""
        chunk = self._reachy_mini.media.get_audio_sample()  # waits up to 20 ms for sound
        if chunk is None:
            return
        # Loudness doesn't need stereo: the two microphones are averaged.
        mono_samples = chunk.mean(axis=1) if chunk.ndim == 2 else chunk
        self._samples_not_read_yet = np.concatenate([self._samples_not_read_yet, mono_samples])

    def _take_stretch(self) -> np.ndarray:
        """Take the oldest full stretch out of the samples not read yet."""
        stretch = self._samples_not_read_yet[: self._samples_per_stretch]
        self._samples_not_read_yet = self._samples_not_read_yet[self._samples_per_stretch :]
        return stretch

    @staticmethod
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

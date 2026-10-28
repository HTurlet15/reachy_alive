"""The hearing sense: how loud the sound is, 20 ms at a time.

The microphones give 16,000 samples per second, each between -1 and 1. Each
stretch of 320 samples becomes one loudness level.
"""

import math
import time

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

    NAME = "hearing"
    # Waiting for the next chunk paces the sense; this floor stops it spinning when the
    # microphones give nothing at once, and still drains a backlog at 200 stretches a second.
    PERIOD_S = 0.005
    STRETCH_S = 0.02
    # A chunk that waited in the microphones' queue comes back at once; for a
    # fresh one, the SDK waits up to 20 ms.
    QUEUED_CHUNK_S = 0.005
    # Dropping old sound never takes longer: the sense would sit deaf.
    MAX_DROP_S = 1.0
    # Read every few milliseconds while switched on: a longer gap between two
    # readings means the page had switched hearing off.
    SWITCHED_OFF_GAP_S = 0.5

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
        self._last_read_at: float | None = None  # None until the first reading

    def is_available(self) -> bool:
        """Return whether the robot has microphones: without any, the sample rate isn't positive."""
        return self._sample_rate_hz > 0

    def _extract_features(
        self, perceived_at: float, robot_moving_itself: bool
    ) -> HearingFeatures | None:
        """Describe the next stretch of sound, or return None if no full stretch came yet.

        The first reading starts the recording. After a long gap, hearing was
        switched off: the sound left over from before is dropped. Read now, it
        would be dated now, and a door slammed minutes ago would be a sudden noise.
        """
        if self._last_read_at is None:
            self._reachy_mini.media.start_recording()
        elif perceived_at - self._last_read_at > self.SWITCHED_OFF_GAP_S:
            self._drop_sound_heard_before()
        self._last_read_at = perceived_at


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

    def _drop_sound_heard_before(self) -> None:
        """Drop the sound not read yet, and the chunks the microphones queued meanwhile.

        Recording never stops: sound keeps queuing in the SDK, up to 500 chunks.
        Queued chunks come back at once; the first one that makes us wait is
        fresh, and the queue is empty.
        """
        self._samples_not_read_yet = np.zeros(0) #We drop the queue of sound not read yet
        give_up_at = time.monotonic() + self.MAX_DROP_S
        while time.monotonic() < give_up_at:
            asked_at = time.monotonic()
            chunk = self._reachy_mini.media.get_audio_sample()
            if chunk is None or time.monotonic() - asked_at > self.QUEUED_CHUNK_S:
                return  # no sound, or fresh sound: nothing old is left

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

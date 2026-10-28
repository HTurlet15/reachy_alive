"""The hearing sense: how loud the sound is, 20 ms at a time.

The microphones give 16,000 samples per second, each between -1 and 1. The
SDK hands them over in chunks of any length, as they arrive, and queues the
chunks not taken yet. The sense pours the samples of the chunks it takes into
its buffer, and cuts them into frames of 20 ms, 320 samples: one loudness
level each.
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
    """Listens to the microphones and describes each frame of sound by its HearingFeatures.

    Sound arrives in SDK chunks of any length: the sense cuts it into frames,
    and times them by how long it has listened.
    """

    NAME = "hearing"
    # Waiting for the next chunk paces the sense; this floor stops it spinning when the
    # microphones give nothing at once, and still drains a backlog at 200 frames a second.
    PERIOD_S = 0.005
    FRAME_S = 0.02
    # An SDK chunk that waited in the queue comes back at once; for a
    # fresh one, the SDK waits up to 20 ms.
    QUEUED_CHUNK_S = 0.005
    # Dropping old sound never takes longer: the sense would sit deaf.
    MAX_DROP_S = 1.0
    # Read every few milliseconds while switched on: a longer gap between two
    # readings means the page had switched hearing off.
    SWITCHED_OFF_GAP_S = 0.5

    def __init__(self, reachy_mini: ReachyMini, shared_state: SharedState) -> None:
        """Size the frames from the microphones' sample rate.

        Args:
            reachy_mini: Connected robot instance, only listened to.
            shared_state: Where the sense learns whether the robot is moving itself.
        """
        super().__init__(reachy_mini, shared_state)
        self._sample_rate_hz = reachy_mini.media.get_input_audio_samplerate()
        self._samples_per_frame = round(self._sample_rate_hz * self.FRAME_S)
        self._sample_buffer = np.zeros(0)
        # The sound's own clock, never reset: chunks can arrive late, the sound itself can't.
        self._time_listened_s = 0.0
        self._last_read_at: float | None = None  # None until the first reading

    def is_available(self) -> bool:
        """Return whether the robot has microphones: without any, the sample rate isn't positive."""
        return self._sample_rate_hz > 0

    def _extract_features(
        self, perceived_at: float, robot_moving_itself: bool
    ) -> HearingFeatures | None:
        """Describe the next frame of sound, or return None if no full frame came yet.

        The first reading starts the recording. After a long gap, hearing was
        switched off: the sound left over from before is dropped. Read now, it
        would be dated now, and a door slammed minutes ago would be a sudden noise.
        """
        if self._last_read_at is None:
            self._reachy_mini.media.start_recording()
        elif perceived_at - self._last_read_at > self.SWITCHED_OFF_GAP_S:
            self._drop_old_sound()
        self._last_read_at = perceived_at

        if not self._has_full_frame():
            self._take_sdk_chunk()
        if not self._has_full_frame():
            return None  # not enough sound yet

        frame = self._take_frame()
        self._time_listened_s += self.FRAME_S
        return HearingFeatures(
            perceived_at=perceived_at,
            time_listened_s=self._time_listened_s,
            level_dbfs=self.loudness_dbfs(frame),
            robot_moving_itself=robot_moving_itself,
        )

    def _drop_old_sound(self) -> None:
        """Drop the samples in the buffer, and the SDK chunks queued meanwhile.

        Recording never stops: sound keeps queuing in the SDK, up to 500 chunks.
        Queued chunks come back at once; the first one that makes us wait is
        fresh, and the queue is empty.
        """
        self._sample_buffer = np.zeros(0)  # ours: taken from the SDK, not cut yet
        give_up_at = time.monotonic() + self.MAX_DROP_S
        while time.monotonic() < give_up_at:
            asked_at = time.monotonic()
            sdk_chunk = self._reachy_mini.media.get_audio_sample()
            if sdk_chunk is None or time.monotonic() - asked_at > self.QUEUED_CHUNK_S:
                return  # no sound, or fresh sound: nothing old is left

    def _has_full_frame(self) -> bool:
        """Return whether the buffer holds a full frame."""
        return len(self._sample_buffer) >= self._samples_per_frame

    def _take_sdk_chunk(self) -> None:
        """Take the next SDK chunk, if any, and pour its samples into the buffer."""
        sdk_chunk = self._reachy_mini.media.get_audio_sample()  # waits up to 20 ms for sound
        if sdk_chunk is None:
            return
        # Loudness doesn't need stereo: the two microphones are averaged.
        mono_samples = sdk_chunk.mean(axis=1) if sdk_chunk.ndim == 2 else sdk_chunk
        self._sample_buffer = np.concatenate([self._sample_buffer, mono_samples])

    def _take_frame(self) -> np.ndarray:
        """Take the oldest full frame out of the buffer."""
        frame = self._sample_buffer[: self._samples_per_frame]
        self._sample_buffer = self._sample_buffer[self._samples_per_frame :]
        return frame

    @staticmethod
    def loudness_dbfs(samples: np.ndarray) -> float:
        """Return how loud a frame of sound is, in dBFS.

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

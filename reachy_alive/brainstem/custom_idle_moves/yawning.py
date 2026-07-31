import time

import numpy as np
from reachy_mini import ReachyMini
from reachy_mini.utils import create_head_pose

from reachy_alive.move import Move


class Yawning(Move):
    """Plays a hand-made yawn: head rises, antennas lower, hold, release."""

    RISE_PITCH_DEG = -20.0
    ANTENNAS_LOWERED_RAD = -1.0
    RISE_DURATION_S = 1.5
    HOLD_DURATION_S = 0.8
    RELEASE_DURATION_S = 1.0

    AUDIO_START_HZ = 500.0
    AUDIO_END_HZ = 180.0
    AUDIO_DURATION_S = 0.8
    AUDIO_VOLUME = 0.3
    AUDIO_CHUNK_SIZE = 1024

    def trigger(self, reachy_mini: ReachyMini) -> None:
        rise_pose = create_head_pose(pitch=self.RISE_PITCH_DEG, degrees=True)
        reachy_mini.goto_target(
            head=rise_pose,
            antennas=[self.ANTENNAS_LOWERED_RAD, -self.ANTENNAS_LOWERED_RAD],
            duration=self.RISE_DURATION_S,
        )

        self._play_yawn_audio(reachy_mini)

        reachy_mini.goto_target(
            head=rise_pose,
            antennas=[self.ANTENNAS_LOWERED_RAD, -self.ANTENNAS_LOWERED_RAD],
            duration=self.HOLD_DURATION_S,
        )
        neutral_pose = create_head_pose(pitch=0.0, degrees=True)
        reachy_mini.goto_target(
            head=neutral_pose, antennas=[0.0, 0.0], duration=self.RELEASE_DURATION_S
        )

    def _play_yawn_audio(self, reachy_mini: ReachyMini) -> None:
        """Generate and play a descending audio, mimicking a yawn."""
        sample_rate = reachy_mini.media.get_output_audio_samplerate()
        audio = self._generate_descending_audio(sample_rate)

        reachy_mini.media.start_playing()
        for i in range(0, len(audio), self.AUDIO_CHUNK_SIZE):
            reachy_mini.media.push_audio_sample(audio[i : i + self.AUDIO_CHUNK_SIZE])
        time.sleep(len(audio) / sample_rate)
        reachy_mini.media.stop_playing()

    def _generate_descending_audio(self, sample_rate: int) -> np.ndarray:
        """Build a sine AUDIO sweeping from AUDIO_START_HZ to AUDIO_END_HZ."""
        t = np.linspace(0, self.AUDIO_DURATION_S, int(sample_rate * self.AUDIO_DURATION_S))
        frequency = np.linspace(self.AUDIO_START_HZ, self.AUDIO_END_HZ, len(t))
        audio = self.AUDIO_VOLUME * np.sin(2 * np.pi * frequency * t)

        fade_samples = int(sample_rate * 0.01)
        fade_in = np.linspace(0, 1, fade_samples)
        fade_out = np.linspace(1, 0, fade_samples)
        audio[:fade_samples] *= fade_in
        audio[-fade_samples:] *= fade_out

        return audio.astype(np.float32)
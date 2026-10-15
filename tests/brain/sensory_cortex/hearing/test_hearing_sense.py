"""Unit tests for HearingSense, with fake microphones that give chosen chunks of sound."""

import math
from unittest.mock import MagicMock

import numpy as np
import pytest

from reachy_alive.brain.sensory_cortex.hearing.hearing_sense import SILENCE_DBFS, HearingSense
from reachy_alive.shared_state import SharedState

SAMPLE_RATE_HZ = 16_000
STRETCH_SAMPLES = 320  # 20 ms at 16 kHz
QUIET = 0.001  # -60 dBFS
LOUD = 0.3  # about -10 dBFS


def sound(amplitude: float, duration_s: float) -> np.ndarray:
    """Return stereo samples of the given loudness: only their size matters to loudness."""
    return np.full((round(duration_s * SAMPLE_RATE_HZ), 2), amplitude)


def chunks_of(samples: np.ndarray, chunk_size: int) -> list[np.ndarray]:
    """Cut samples into the chunks the microphones would give, one per call."""
    return [samples[i : i + chunk_size] for i in range(0, len(samples), chunk_size)]


def make_sense(chunks: list, sample_rate_hz: int = SAMPLE_RATE_HZ):
    """Build a sense on fake microphones that give `chunks`, then nothing."""
    reachy_mini = MagicMock()
    reachy_mini.media.get_input_audio_samplerate.return_value = sample_rate_hz
    reachy_mini.media.get_audio_sample.side_effect = chunks + [None] * 100
    state = SharedState()
    return HearingSense(reachy_mini, state), state, reachy_mini


def features_from(sense: HearingSense, readings: int) -> list:
    """Take `readings` readings, 10 ms apart, and return the features of the stretches they gave."""
    readings = [sense.read_once(i * 0.01) for i in range(readings)]
    return [features for features in readings if features is not None]


# loudness_dbfs


def test_silence_is_the_quietest_level():
    assert HearingSense.loudness_dbfs(np.zeros(320)) == SILENCE_DBFS


def test_a_full_scale_square_wave_is_0_dbfs():
    assert math.isclose(HearingSense.loudness_dbfs(np.array([1.0, -1.0] * 160)), 0.0)


def test_halving_the_sound_lowers_it_by_6_db():
    full = HearingSense.loudness_dbfs(np.array([1.0, -1.0] * 160))
    half = HearingSense.loudness_dbfs(np.array([0.5, -0.5] * 160))

    assert math.isclose(full - half, 20 * math.log10(2))


# Stretches


def test_each_stretch_of_sound_gets_its_own_features():
    sense, _, _ = make_sense(chunks_of(sound(QUIET, 0.1), STRETCH_SAMPLES))

    stretches = features_from(sense, 10)

    assert len(stretches) == 5
    assert stretches[0].level_dbfs == pytest.approx(-60.0)


def test_the_features_are_dated_by_the_reading_and_timed_by_the_sound():
    sense, _, _ = make_sense(chunks_of(sound(QUIET, 0.04), STRETCH_SAMPLES))

    stretches = [sense.read_once(5.0), sense.read_once(5.5)]

    assert [features.t for features in stretches] == [5.0, 5.5]
    assert [features.time_listened_s for features in stretches] == pytest.approx([0.02, 0.04])


def test_a_loud_stretch_reads_loud():
    sense, _, _ = make_sense(chunks_of(sound(LOUD, 0.02), STRETCH_SAMPLES))

    assert sense.read_once(0.0).level_dbfs == pytest.approx(20 * math.log10(LOUD))


def test_small_chunks_are_gathered_into_stretches():
    sense, _, _ = make_sense(chunks_of(sound(QUIET, 0.1), 123))

    assert len(features_from(sense, 20)) == 5


def test_a_big_chunk_gives_one_stretch_per_reading():
    sense, _, reachy_mini = make_sense([sound(QUIET, 0.1)])

    stretches = features_from(sense, 5)

    assert len(stretches) == 5
    assert reachy_mini.media.get_audio_sample.call_count == 1


def test_no_features_without_sound():
    sense, _, _ = make_sense([])

    assert sense.read_once(0.0) is None


# The robot's own moves


def test_the_features_say_when_a_move_plays():
    sense, state, _ = make_sense(chunks_of(sound(QUIET, 0.02), STRETCH_SAMPLES))
    state.set_move_playing(True)

    assert sense.read_once(0.0).robot_moving_itself is True


def test_the_features_say_when_the_robot_just_moved_itself():
    sense, state, _ = make_sense(chunks_of(sound(QUIET, 0.04), STRETCH_SAMPLES))
    state.set_move_playing(True)
    state.set_move_playing(False)
    ended_at = state.last_move_ended_at()

    assert sense.read_once(ended_at + 0.3).robot_moving_itself is True  # within SETTLE_AFTER_MOVE_S
    assert sense.read_once(ended_at + 1.0).robot_moving_itself is False


# Microphones


def test_without_microphones_the_sense_is_not_available():
    sense, _, _ = make_sense([], sample_rate_hz=-1)

    assert sense.is_available() is False


def test_opening_and_closing_start_and_stop_the_recording():
    sense, _, reachy_mini = make_sense([])

    sense.open()
    sense.close()

    reachy_mini.media.start_recording.assert_called_once()
    reachy_mini.media.stop_recording.assert_called_once()
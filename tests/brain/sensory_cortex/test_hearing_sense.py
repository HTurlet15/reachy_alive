"""Unit tests for HearingSense, with fake microphones that give chosen chunks of sound."""

import logging
from unittest.mock import MagicMock

import numpy as np

from reachy_alive.brain.sensory_cortex.hearing import HearingSense
from reachy_alive.shared_state import SharedState

SAMPLE_RATE_HZ = 16_000
QUIET = 0.001  # about -60 dBFS
LOUD = 0.3  # about -10 dBFS


def sound(amplitude: float, duration_s: float) -> np.ndarray:
    """Return stereo samples of the given loudness: only their size matters to loudness."""
    return np.full((round(duration_s * SAMPLE_RATE_HZ), 2), amplitude)


def chunks_of(samples: np.ndarray, chunk_size: int) -> list[np.ndarray]:
    """Cut samples into the chunks the microphones would give, one per reading."""
    return [samples[i : i + chunk_size] for i in range(0, len(samples), chunk_size)]


def make_sense(chunks: list, sample_rate_hz: int = SAMPLE_RATE_HZ):
    """Build a sense on fake microphones that give `chunks`, one per reading."""
    reachy_mini = MagicMock()
    reachy_mini.media.get_input_audio_samplerate.return_value = sample_rate_hz
    reachy_mini.media.get_audio_sample.side_effect = chunks + [None] * 10
    state = SharedState()
    return HearingSense(reachy_mini, state), state


def read_all(sense: HearingSense, count: int) -> None:
    """Take `count` readings, 10 ms apart."""
    for i in range(count):
        sense.read_once(i * 0.01)


def test_a_quiet_room_records_nothing():
    chunks = chunks_of(sound(QUIET, 3.0), 320)
    sense, state = make_sense(chunks)

    read_all(sense, len(chunks))

    assert state.last_sudden_noise_at() is None


def test_a_clap_is_recorded():
    chunks = chunks_of(np.concatenate([sound(QUIET, 2.0), sound(LOUD, 0.02)]), 320)
    sense, state = make_sense(chunks)

    read_all(sense, len(chunks))

    assert state.last_sudden_noise_at() == (len(chunks) - 1) * 0.01


def test_chunks_of_any_length_are_cut_into_stretches():
    chunks = chunks_of(np.concatenate([sound(QUIET, 2.0), sound(LOUD, 0.02)]), 123)
    sense, state = make_sense(chunks)

    read_all(sense, len(chunks))

    assert state.last_sudden_noise_at() is not None


def test_a_noise_while_a_move_plays_is_not_recorded():
    chunks = chunks_of(np.concatenate([sound(QUIET, 2.0), sound(LOUD, 0.02)]), 320)
    sense, state = make_sense(chunks)
    state.set_move_playing(True)

    read_all(sense, len(chunks))

    assert state.last_sudden_noise_at() is None


def test_a_noise_right_after_a_move_is_not_recorded():
    quiet_chunks = chunks_of(sound(QUIET, 2.0), 320)
    clap_chunks = chunks_of(sound(LOUD, 0.02), 320)
    sense, state = make_sense(quiet_chunks + clap_chunks)
    state.set_move_playing(True)
    read_all(sense, len(quiet_chunks))
    state.set_move_playing(False)

    sense.read_once(len(quiet_chunks) * 0.01)  # 10 ms after the move

    assert state.last_sudden_noise_at() is None


def test_without_microphones_the_sense_says_so_and_stops(caplog):
    sense, state = make_sense([], sample_rate_hz=-1)

    with caplog.at_level(logging.INFO):
        sense.run(MagicMock())

    assert "No microphones" in caplog.text

"""Unit tests for HearingSense, with fake microphones that give chosen chunks of sound."""

import itertools
import math
import threading
import time
from unittest.mock import MagicMock

import numpy as np
import pytest

from reachy_alive.brain.sensory_cortex.hearing.hearing_sense import SILENCE_DBFS, HearingSense
from reachy_alive.brain.sensory_cortex.sense_manager import SenseManager
from reachy_alive.shared_state import SharedState

SAMPLE_RATE_HZ = 16_000
FRAME_SAMPLES = 320  # 20 ms at 16 kHz
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
    """Take `readings` readings, 10 ms apart, and return the features of the frames they gave."""
    readings = [sense.perceive(i * 0.01) for i in range(readings)]
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


# Frames


def test_each_frame_of_sound_gets_its_own_features():
    sense, _, _ = make_sense(chunks_of(sound(QUIET, 0.1), FRAME_SAMPLES))

    frames = features_from(sense, 10)

    assert len(frames) == 5
    assert frames[0].level_dbfs == pytest.approx(-60.0)


def test_the_features_are_dated_by_the_reading_and_timed_by_the_sound():
    sense, _, _ = make_sense(chunks_of(sound(QUIET, 0.04), FRAME_SAMPLES))

    frames = [sense.perceive(5.0), sense.perceive(5.2)]

    assert [features.perceived_at for features in frames] == [5.0, 5.2]
    assert [features.time_listened_s for features in frames] == pytest.approx([0.02, 0.04])


def test_a_loud_frame_reads_loud():
    sense, _, _ = make_sense(chunks_of(sound(LOUD, 0.02), FRAME_SAMPLES))

    assert sense.perceive(0.0).level_dbfs == pytest.approx(20 * math.log10(LOUD))


def test_small_chunks_are_gathered_into_frames():
    sense, _, _ = make_sense(chunks_of(sound(QUIET, 0.1), 123))

    assert len(features_from(sense, 20)) == 5


def test_a_big_chunk_gives_one_frame_per_reading():
    sense, _, reachy_mini = make_sense([sound(QUIET, 0.1)])

    frames = features_from(sense, 5)

    assert len(frames) == 5
    assert reachy_mini.media.get_audio_sample.call_count == 1


def test_no_features_without_sound():
    sense, _, _ = make_sense([])

    assert sense.perceive(0.0) is None


# The robot's own moves


def test_the_features_say_when_a_move_plays():
    sense, state, _ = make_sense(chunks_of(sound(QUIET, 0.02), FRAME_SAMPLES))
    state.set_move_playing(True)

    assert sense.perceive(0.0).robot_moving_itself is True


def test_the_features_say_when_the_robot_just_moved_itself():
    sense, state, _ = make_sense(chunks_of(sound(QUIET, 0.04), FRAME_SAMPLES))
    state.set_move_playing(True)
    state.set_move_playing(False)
    ended_at = state.last_move_ended_at()

    assert sense.perceive(ended_at + 0.3).robot_moving_itself is True  # within SETTLE_AFTER_MOVE_S
    assert sense.perceive(ended_at + 0.6).robot_moving_itself is False


# Microphones


def test_without_microphones_the_sense_is_not_available():
    sense, _, _ = make_sense([], sample_rate_hz=-1)

    assert sense.is_available() is False


def test_the_first_reading_starts_the_recording_once():
    sense, _, reachy_mini = make_sense([])

    sense.perceive(0.0)
    sense.perceive(0.01)

    reachy_mini.media.start_recording.assert_called_once()


def test_sound_left_over_when_switched_off_is_not_read_once_switched_back_on():
    sense, _, _ = make_sense([sound(LOUD, 0.04)])  # one chunk: two frames
    sense.perceive(0.0)  # the first frame is read, the second waits

    # Hearing switched off for a minute: no reading meanwhile.

    assert sense.perceive(60.0) is None  # read now, it would be dated now


def test_a_short_gap_between_readings_keeps_the_sound():
    sense, _, _ = make_sense([sound(LOUD, 0.04)])
    sense.perceive(0.0)

    assert sense.perceive(0.1) is not None  # the robot was just slow, not switched off


def microphones_with_a_queue(queued: list, fresh: np.ndarray):
    """Fake microphones that queued chunks while the sense was off.

    Queued chunks come back at once; fresh ones after a wait, as from the SDK.
    """
    queue = list(queued)

    def get_audio_sample():
        if queue:
            return queue.pop(0)
        time.sleep(0.02)
        return fresh

    return get_audio_sample


def test_sound_queued_while_switched_off_is_dropped():
    # Through WebRTC, stop_recording does nothing: a noise made while
    # switched off waits in the queue.
    sense, _, reachy_mini = make_sense([sound(QUIET, 0.02)])
    sense.perceive(0.0)
    queued = chunks_of(sound(LOUD, 1.0), FRAME_SAMPLES)
    fresh = sound(QUIET, 0.02)
    reachy_mini.media.get_audio_sample.side_effect = microphones_with_a_queue(queued, fresh)

    assert sense.perceive(60.0).level_dbfs == pytest.approx(-60.0)


def test_dropping_queued_sound_gives_up_after_max_drop_s(monkeypatch):
    monkeypatch.setattr(HearingSense, "MAX_DROP_S", 0.05)
    sense, _, reachy_mini = make_sense([sound(QUIET, 0.02)])
    sense.perceive(0.0)
    chunk = sound(QUIET, 0.02)
    reachy_mini.media.get_audio_sample.side_effect = itertools.repeat(chunk)  # never empties
    started_at = time.monotonic()

    sense.perceive(60.0)

    assert time.monotonic() - started_at < 0.5


def test_microphones_that_give_nothing_at_once_do_not_make_the_sense_spin():
    sense, _, reachy_mini = make_sense([])
    reachy_mini.media.get_audio_sample.side_effect = itertools.repeat(None)  # no wait, ever
    stop_event = threading.Event()
    threading.Timer(0.2, stop_event.set).start()

    SenseManager.run_sense(sense, [], stop_event)

    # Paced by PERIOD_S, 0.2 s holds about 40 reads; spinning would make thousands.
    assert reachy_mini.media.get_audio_sample.call_count < 100

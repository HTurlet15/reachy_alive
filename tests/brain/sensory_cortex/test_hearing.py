"""Unit tests for loudness_dbfs and SuddenNoiseDetector, on made-up sounds.

The detector reads one loudness level per 20 ms stretch of sound, as the
sense will feed it.
"""

import math

import numpy as np

from reachy_alive.brain.sensory_cortex.hearing import (
    SILENCE_DBFS,
    SuddenNoiseDetector,
    loudness_dbfs,
)

STRETCH_S = 0.02  # one loudness level every 20 ms


def noise_starts(levels_dbfs: list[float]) -> list[float]:
    """Feed one level per stretch to a fresh detector; return when sudden noises started."""
    detector = SuddenNoiseDetector()
    return [
        round(i * STRETCH_S, 2)
        for i, level_dbfs in enumerate(levels_dbfs)
        if detector.update(i * STRETCH_S, level_dbfs)
    ]


def steady(level_dbfs: float, duration_s: float) -> list[float]:
    """Return the same level for every stretch of duration_s."""
    return [level_dbfs] * round(duration_s / STRETCH_S)


# loudness_dbfs


def test_silence_is_the_quietest_level():
    assert loudness_dbfs(np.zeros(320)) == SILENCE_DBFS


def test_a_full_scale_square_wave_is_0_dbfs():
    assert math.isclose(loudness_dbfs(np.array([1.0, -1.0] * 160)), 0.0)


def test_halving_the_sound_lowers_it_by_6_db():
    full = loudness_dbfs(np.array([1.0, -1.0] * 160))
    half = loudness_dbfs(np.array([0.5, -0.5] * 160))

    assert math.isclose(full - half, 20 * math.log10(2))


# SuddenNoiseDetector


def test_a_steady_room_is_quiet():
    assert noise_starts(steady(-60.0, 5.0)) == []


def test_a_clap_in_a_quiet_room_is_a_sudden_noise():
    levels = steady(-60.0, 2.0) + [-10.0] + steady(-60.0, 1.0)

    assert noise_starts(levels) == [2.0]


def test_a_clap_in_a_louder_room_still_counts():
    levels = steady(-30.0, 2.0) + [-3.0] + steady(-30.0, 1.0)

    assert noise_starts(levels) == [2.0]


def test_a_sound_rising_over_seconds_is_not_sudden():
    # 40 dB over 5 s: the background trails 8 dB/s x 2 s = 16 dB behind.
    rising_over_5_s = list(np.linspace(-60.0, -20.0, 250))
    levels = steady(-60.0, 2.0) + rising_over_5_s + steady(-20.0, 2.0)

    assert noise_starts(levels) == []


def test_a_noise_that_lasts_is_reported_once():
    levels = steady(-60.0, 2.0) + steady(-10.0, 0.3) + steady(-60.0, 1.0)

    assert noise_starts(levels) == [2.0]


def test_two_claps_apart_are_two_noises():
    levels = steady(-60.0, 2.0) + [-10.0] + steady(-60.0, 1.0) + [-10.0] + steady(-60.0, 1.0)

    assert noise_starts(levels) == [2.0, 3.02]


def test_the_background_follows_a_room_that_got_louder():
    # After 10 s at -30 dBFS, a jump to -15 is only 15 dB above the background.
    levels = steady(-60.0, 2.0) + list(np.linspace(-60.0, -30.0, 250)) + steady(-30.0, 10.0)

    assert noise_starts(levels + [-15.0]) == []

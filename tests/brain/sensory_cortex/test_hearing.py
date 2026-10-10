"""Unit tests for loudness_dbfs and SuddenNoiseDetector.

The detector is tested on made-up levels and on a recording from the robot.
It reads one loudness level per 20 ms stretch of sound, as the sense feeds it.
"""

import csv
import math
from pathlib import Path

import numpy as np

from reachy_alive.brain.sensory_cortex.hearing import (
    SILENCE_DBFS,
    SuddenNoiseDetector,
    loudness_dbfs,
)

DATA = Path(__file__).parent / "data"
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


# SuddenNoiseDetector: a loud sound

QUIET_ROOM_DBFS = -60.0
CLAP_DBFS = -10.0


def quiet_room_with(duration_s: float, sounds: dict[float, float]) -> list[float]:
    """Return the levels of a quiet room with short sounds in it.

    Args:
        duration_s: How long the room is listened to, in seconds.
        sounds: One stretch-long sound per entry: {time in seconds: level in dBFS}.
    """
    levels = steady(QUIET_ROOM_DBFS, duration_s)
    for t, level_dbfs in sounds.items():
        levels[round(t / STRETCH_S)] = level_dbfs
    return levels


def test_a_steady_room_is_quiet():
    assert noise_starts(steady(QUIET_ROOM_DBFS, 5.0)) == []


def test_a_clap_in_a_quiet_room_is_a_sudden_noise():
    assert noise_starts(quiet_room_with(3.0, {2.0: CLAP_DBFS})) == [2.0]


def test_a_clap_in_a_louder_room_still_counts():
    levels = steady(-40.0, 2.0) + [-5.0] + steady(-40.0, 1.0)

    assert noise_starts(levels) == [2.0]


def test_a_sentence_starting_in_a_quiet_room_is_not_sudden():
    # Measured on the robot: the start of a sentence jumps about 26 dB.
    levels = steady(QUIET_ROOM_DBFS, 2.0) + steady(-34.0, 0.5) + steady(QUIET_ROOM_DBFS, 1.0)

    assert noise_starts(levels) == []


def test_a_sound_rising_over_seconds_is_not_sudden():
    # 40 dB over 5 s: the background trails 8 dB/s x 2 s = 16 dB behind.
    rising_over_5_s = list(np.linspace(-60.0, -20.0, 250))
    levels = steady(QUIET_ROOM_DBFS, 2.0) + rising_over_5_s + steady(-20.0, 2.0)

    assert noise_starts(levels) == []


def test_the_background_follows_a_room_that_got_louder():
    # After 10 s at -30 dBFS, a jump to -15 is only 15 dB above the background.
    levels = steady(QUIET_ROOM_DBFS, 2.0) + list(np.linspace(-60.0, -30.0, 250))
    levels += steady(-30.0, 10.0)

    assert noise_starts(levels + [-15.0]) == []


def test_a_noise_that_lasts_is_reported_once():
    levels = steady(QUIET_ROOM_DBFS, 2.0) + steady(CLAP_DBFS, 0.3) + steady(QUIET_ROOM_DBFS, 1.0)

    assert noise_starts(levels) == [2.0]


def test_a_room_getting_much_louder_at_once_is_reported_once():
    vacuum_switched_on = steady(QUIET_ROOM_DBFS, 2.0) + steady(-10.0, 10.0)

    assert noise_starts(vacuum_switched_on) == [2.0]


# SuddenNoiseDetector: habituation


def test_of_three_claps_in_a_row_only_the_first_is_sudden():
    claps_3_s_apart = {2.0: CLAP_DBFS, 5.0: CLAP_DBFS, 8.0: CLAP_DBFS}

    assert noise_starts(quiet_room_with(10.0, claps_3_s_apart)) == [2.0]


def test_claps_far_apart_are_each_sudden():
    claps_30_s_apart = {2.0: CLAP_DBFS, 32.0: CLAP_DBFS}

    assert noise_starts(quiet_room_with(35.0, claps_30_s_apart)) == [2.0, 32.0]


def test_a_door_slammed_again_minutes_later_is_sudden_again():
    door_slams = {2.0: -5.0, 302.0: -5.0}

    assert noise_starts(quiet_room_with(305.0, door_slams)) == [2.0, 302.0]


def test_a_much_louder_bang_right_after_claps_is_sudden():
    # The claps jump 40 dB, the bang 55 dB: much louder than what we got used to.
    claps_then_a_bang = {2.0: -20.0, 5.0: -20.0, 8.0: -5.0}

    assert noise_starts(quiet_room_with(10.0, claps_then_a_bang)) == [2.0, 8.0]


# A recording from the robot's microphones (sprint B, through WebRTC from a
# laptop): one loudness level per 20 ms, no sound kept. hearing_levels.csv
# follows a script, timed by the clock printed on screen: silence until 10 s;
# a mouse put down at 10, 13 and 16 s on the robot's table, then at 20, 23 and
# 26 s on another table; talking from 30 to 40 s; claps at 48, 51 and 54 s;
# a knuckle knocking on the robot's table at 58 s.


def recorded_noise_starts(name: str) -> list[float]:
    """Feed a recording to a fresh detector; return when sudden noises started.

    The detector is timed by the sound heard; the times returned are on the
    clock printed on screen, to compare with the script.
    """
    detector = SuddenNoiseDetector()
    with open(DATA / name) as f:
        return [
            float(row["clock_s"])
            for row in csv.DictReader(f)
            if detector.update(float(row["sound_heard_s"]), float(row["level_dbfs"]))
        ]


def noises_between(start_s: float, end_s: float) -> list[float]:
    """When sudden noises started in hearing_levels.csv, between two clock readings."""
    return [t for t in recorded_noise_starts("hearing_levels.csv") if start_s <= t < end_s]


def test_nothing_is_heard_before_the_script_starts():
    assert noises_between(0.0, 10.0) == []


def test_a_mouse_put_down_hard_is_sudden_once():
    # The first three, on the robot's table, didn't jump high enough. The
    # loudest, at 20 s, did; the two after it were expected.
    assert len(noises_between(10.0, 28.0)) == 1


def test_talking_is_not_a_sudden_noise():
    assert noises_between(30.0, 45.0) == []


def test_of_the_three_claps_only_the_first_is_sudden():
    assert len(noises_between(48.0, 57.0)) == 1


def test_a_knock_moments_after_the_claps_is_expected():
    # As loud as the claps, 5 s after the last one.
    assert noises_between(58.0, 61.0) == []
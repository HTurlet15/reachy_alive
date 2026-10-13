"""Unit tests for SuddenNoiseDetector.

The detector is tested on made-up levels and on a recording from the robot.
It reads one frame per 20 ms stretch of sound, as the sense hands them.
"""

import csv
from pathlib import Path
from unittest.mock import MagicMock

import numpy as np

from reachy_alive.brain.sensory_cortex.hearing.hearing_frame import HearingFrame
from reachy_alive.brain.sensory_cortex.hearing.sudden_noise_detector import SuddenNoiseDetector
from reachy_alive.shared_state import HearingFacts

DATA = Path(__file__).parent.parent / "data"
STRETCH_S = 0.02  # one frame every 20 ms


def recorded_noises(frames: list[HearingFrame]) -> list[float]:
    """Feed frames to a fresh detector; return when it recorded each sudden noise.

    The facts only keep the last noise: fake facts keep every call instead.
    """
    facts = MagicMock(spec=HearingFacts)
    detector = SuddenNoiseDetector(facts)
    for frame in frames:
        detector.update(frame)
    return [call.args[0] for call in facts.record_sudden_noise.call_args_list]


def noise_starts(levels_dbfs: list[float], robot_moving_itself: bool = False) -> list[float]:
    """Feed one level per stretch; return when sudden noises started.

    Each stretch is read the moment its sound ends: both clocks agree.
    """
    return recorded_noises(
        [
            HearingFrame(
                t=round(i * STRETCH_S, 2),
                time_listened_s=i * STRETCH_S,
                level_dbfs=level_dbfs,
                robot_moving_itself=robot_moving_itself,
            )
            for i, level_dbfs in enumerate(levels_dbfs)
        ]
    )


def steady(level_dbfs: float, duration_s: float) -> list[float]:
    """Return the same level for every stretch of duration_s."""
    return [level_dbfs] * round(duration_s / STRETCH_S)


# A loud sound

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


def test_a_sudden_noise_is_recorded_when_its_stretch_was_read():
    facts = HearingFacts()
    detector = SuddenNoiseDetector(facts)
    quiet = HearingFrame(
        t=10.0, time_listened_s=0.02, level_dbfs=QUIET_ROOM_DBFS, robot_moving_itself=False
    )
    clap = HearingFrame(
        t=10.02, time_listened_s=0.04, level_dbfs=CLAP_DBFS, robot_moving_itself=False
    )

    detector.update(quiet)
    detector.update(clap)

    assert facts.last_sudden_noise_at() == 10.02  # t, not the sound's clock


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


def test_a_clap_while_the_robot_moves_itself_is_not_recorded():
    levels = quiet_room_with(3.0, {2.0: CLAP_DBFS})

    assert noise_starts(levels, robot_moving_itself=True) == []


# Habituation


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

    Each row is a frame: read at clock_s, the clock printed on screen, to
    compare with the script; time_listened_s is the sound's own clock.
    """
    with open(DATA / name) as f:
        frames = [
            HearingFrame(
                t=float(row["clock_s"]),
                time_listened_s=float(row["time_listened_s"]),
                level_dbfs=float(row["level_dbfs"]),
                robot_moving_itself=False,
            )
            for row in csv.DictReader(f)
        ]
    return recorded_noises(frames)


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

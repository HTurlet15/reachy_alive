"""Unit tests for AntennaPush (one antenna) and AntennaPushDetector (both, writing facts).

A sample is (t, target_rad, present_rad): when the antenna was read, where
it was sent, and where it was measured. AntennaPush is tested first on
made-up samples, one rule per test, then on recordings from the robot.
"""

import csv
import math
from pathlib import Path

from reachy_alive.brain.sensory_cortex.touch.antenna_push_detector import (
    AntennaPush,
    AntennaPushDetector,
)
from reachy_alive.brain.sensory_cortex.touch.touch_frame import TouchFrame
from reachy_alive.shared_state import TouchFacts

DATA = Path(__file__).parent.parent / "data"
RIGHT, LEFT = 0, 1  # the SDK's order for the antennas, on the real robot
MOTOR_DELAY_S = 0.08  # how far behind its target a healthy motor runs


def times_at_50_hz(duration_s: float) -> list[float]:
    """Return the times of 50 readings per second, from 0 to duration_s."""
    return [i / 50 for i in range(int(duration_s * 50))]


def breathing_sway_rad(t: float) -> float:
    """Return the antenna sway of breathing at time t: ±15° at 0.25 Hz, in radians."""
    return math.radians(15.0) * math.sin(2 * math.pi * 0.25 * t)


def push_starts(samples, push: AntennaPush | None = None) -> list[float]:
    """Feed samples to one AntennaPush and return when each push started.

    A push held for several samples counts once.
    """
    push = push or AntennaPush()
    starts = []
    for t, target_rad, present_rad in samples:
        pushed_since = push.update(t, target_rad, present_rad)
        if pushed_since is not None and pushed_since not in starts:
            starts.append(pushed_since)
    return starts


def recorded_samples(name: str, antenna: int) -> list[tuple[float, float, float]]:
    """Return the samples of one antenna from a recording in tests' data folder."""
    with open(DATA / name) as f:
        return [
            (float(r["t_s"]), float(r[f"target_{antenna}"]), float(r[f"present_{antenna}"]))
            for r in csv.DictReader(f)
        ]


def stretches_between_moves(samples) -> list[list[tuple[float, float, float]]]:
    """Split samples where the sense went quiet for a move (a gap over 0.1 s).

    The detector forgets its pushes during each move, as these tests do.
    """
    stretches = [[samples[0]]]
    for previous, sample in zip(samples, samples[1:]):
        if sample[0] - previous[0] > 0.1:
            stretches.append([])
        stretches[-1].append(sample)
    return stretches


# Made-up samples: one rule per test.


def test_an_antenna_on_its_target_is_not_pushed():
    on_target = [(t, math.radians(10.0), math.radians(10.0)) for t in times_at_50_hz(2.0)]

    assert push_starts(on_target) == []


def test_a_motor_reaching_its_targets_late_is_not_pushed():
    late_by_the_motor_delay = [
        (t, breathing_sway_rad(t), breathing_sway_rad(t - MOTOR_DELAY_S))
        for t in times_at_50_hz(8.0)
    ]

    assert push_starts(late_by_the_motor_delay) == []


def test_measurements_late_by_up_to_200_ms_are_not_a_push():
    late_by_200_ms = [
        (t, breathing_sway_rad(t), breathing_sway_rad(t - 0.2)) for t in times_at_50_hz(8.0)
    ]

    assert push_starts(late_by_200_ms) == []


def test_moving_the_antenna_away_starts_a_push():
    moved_10_degrees_at_1_s = [
        (t, 0.0, 0.0 if t < 1.0 else math.radians(10.0)) for t in times_at_50_hz(2.0)
    ]

    assert push_starts(moved_10_degrees_at_1_s) == [1.0]


def test_a_push_lasts_until_the_gap_falls_under_the_release_threshold():
    # With the class's thresholds: a push starts at 5° and ends under 3°.
    push = AntennaPush()
    for t in times_at_50_hz(1.0):
        push.update(t, 0.0, 0.0)

    assert push.update(1.00, 0.0, math.radians(6.0)) == 1.00  # reaches 5°: starts
    assert push.update(1.02, 0.0, math.radians(4.0)) == 1.00  # between 3° and 5°: goes on
    assert push.update(1.04, 0.0, math.radians(2.0)) is None  # under 3°: ends


def test_nothing_is_judged_before_a_target_was_sent_long_enough_ago():
    assert AntennaPush().update(0.00, 0.0, math.radians(30.0)) is None


# Recordings from the robot, from the sprint B spike:
# - antennas_hold.csv: both antennas held still; three short pushes on the
#   left, three on the right, then the left held pushed twice.
# - antennas_sway_check.csv: both antennas swaying like breathing, untouched.
# - antennas_sway.csv: the same, untouched for the first 20 s.
# - antennas_in_app.csv: recorded by AntennasSense in the app, run from a
#   laptop, untouched, with moves in between.
# The right antenna of that robot catches in its gearbox: it moves in jerks.


def test_finds_every_push_on_each_antenna():
    assert len(push_starts(recorded_samples("antennas_hold.csv", LEFT))) == 5
    assert len(push_starts(recorded_samples("antennas_hold.csv", RIGHT))) == 3


def test_swaying_antennas_are_not_pushed():
    assert push_starts(recorded_samples("antennas_sway_check.csv", LEFT)) == []
    assert push_starts(recorded_samples("antennas_sway_check.csv", RIGHT)) == []


def test_without_the_motor_delay_the_jerky_antenna_reads_as_pushed():
    no_delay = AntennaPush()
    no_delay.MIN_DELAY_S = no_delay.MAX_DELAY_S = 0.0

    assert push_starts(recorded_samples("antennas_sway_check.csv", RIGHT), no_delay) != []


def test_the_left_antenna_is_not_pushed_while_swaying_untouched():
    # Only the left: on this recording, the right antenna's jerks read as pushes.
    untouched = [s for s in recorded_samples("antennas_sway.csv", LEFT) if s[0] < 20.0]

    assert push_starts(untouched) == []


def test_the_left_antenna_is_not_pushed_in_the_app_despite_frozen_measurements():
    # Over the network, the measured positions sometimes stop updating for
    # up to 0.26 s while the targets keep moving.
    for stretch in stretches_between_moves(recorded_samples("antennas_in_app.csv", LEFT)):
        assert push_starts(stretch) == []


# AntennaPushDetector: both antennas, from frames to facts.

NEUTRAL_RAD = (-0.17, 0.17)  # (right, left)


def follow(detector: AntennaPushDetector, start_s: float, duration_s: float, measured_rad,
           robot_moving_itself: bool = False) -> float:
    """Hand a frame every 20 ms, antennas sent to NEUTRAL_RAD; return the time after."""
    t = start_s
    while t < start_s + duration_s - 1e-9:
        detector.update(TouchFrame(t, NEUTRAL_RAD, measured_rad, robot_moving_itself))
        t = round(t + 0.02, 6)
    return t


def test_a_push_is_recorded_on_the_antenna_moved_away():
    facts = TouchFacts()
    detector = AntennaPushDetector(facts)
    t = follow(detector, 0.0, 0.5, NEUTRAL_RAD)

    follow(detector, t, 0.02, (NEUTRAL_RAD[0], NEUTRAL_RAD[1] + math.radians(10.0)))

    assert facts.antenna_pushed_since("left") == t
    assert facts.antenna_pushed_since("right") is None


def test_a_released_antenna_is_no_longer_pushed():
    facts = TouchFacts()
    detector = AntennaPushDetector(facts)
    t = follow(detector, 0.0, 0.5, NEUTRAL_RAD)
    t = follow(detector, t, 0.2, (NEUTRAL_RAD[0] + math.radians(10.0), NEUTRAL_RAD[1]))

    follow(detector, t, 0.02, NEUTRAL_RAD)

    assert facts.antenna_pushed_since("right") is None


def test_nothing_is_pushed_while_the_robot_moves_itself():
    facts = TouchFacts()
    detector = AntennaPushDetector(facts)
    t = follow(detector, 0.0, 0.5, NEUTRAL_RAD)
    far_away = (NEUTRAL_RAD[0] + math.radians(30.0), NEUTRAL_RAD[1] + math.radians(30.0))

    follow(detector, t, 0.5, far_away, robot_moving_itself=True)

    assert facts.antenna_pushed_since("right") is None
    assert facts.antenna_pushed_since("left") is None


def test_a_push_is_forgotten_once_the_robot_moves_itself():
    facts = TouchFacts()
    detector = AntennaPushDetector(facts)
    t = follow(detector, 0.0, 0.5, NEUTRAL_RAD)
    pushed = (NEUTRAL_RAD[0], NEUTRAL_RAD[1] + math.radians(10.0))
    t = follow(detector, t, 0.2, pushed)

    follow(detector, t, 0.02, pushed, robot_moving_itself=True)

    assert facts.antenna_pushed_since("left") is None

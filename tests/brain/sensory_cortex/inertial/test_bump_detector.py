"""Unit tests for BumpDetector, on made-up readings and on recordings from the robot."""

import csv
from pathlib import Path

from reachy_alive.brain.sensory_cortex.inertial.bump_detector import BumpDetector
from reachy_alive.brain.sensory_cortex.inertial.inertial_features import InertialFeatures
from reachy_alive.shared_state import InertialFacts

DATA = Path(__file__).parent.parent / "data"
STILL = (0.0, 0.0, 9.81)
JOLT = (0.0, 0.0, 15.0)


def load_accelerometer(name: str) -> list[tuple[float, tuple[float, float, float]]]:
    """Load (t, (ax, ay, az)) readings from a recording in tests' data folder."""
    with open(DATA / name) as f:
        return [
            (float(r["t_s"]), (float(r["ax"]), float(r["ay"]), float(r["az"])))
            for r in csv.DictReader(f)
        ]


def bump_times(readings, robot_moving_itself: bool = False) -> list[float]:
    """Feed readings to a fresh BumpDetector and return when it recorded bumps."""
    facts = InertialFacts()
    detector = BumpDetector(facts)
    times = []
    for t, accelerometer in readings:
        detector.update(InertialFeatures(t, accelerometer, robot_moving_itself))
        if facts.last_bump_at() == t:
            times.append(t)
    return times


def test_gravity_alone_is_no_bump():
    assert bump_times([(0.0, STILL)]) == []


def test_a_tilted_head_is_no_bump():
    # Tilting the head moves gravity to another axis without changing its norm.
    assert bump_times([(0.0, (9.81, 0.0, 0.0))]) == []


def test_a_jolt_is_a_bump():
    assert bump_times([(0.0, JOLT)]) == [0.0]


def test_a_dip_below_gravity_is_a_bump_too():
    assert bump_times([(0.0, (0.0, 0.0, 4.0))]) == [0.0]


def test_a_bump_is_recorded_once_while_the_head_rings():
    ringing = [(0.00, JOLT), (0.02, (0.0, 0.0, 4.0)), (0.20, (0.0, 0.0, 14.0))]

    assert bump_times(ringing) == [0.0]


def test_a_second_bump_after_the_refractory_period_counts():
    after_refractory_s = BumpDetector.REFRACTORY_S + 0.1

    assert bump_times([(0.0, JOLT), (after_refractory_s, JOLT)]) == [0.0, after_refractory_s]


def test_nothing_is_felt_while_the_robot_moves_itself():
    assert bump_times([(0.0, JOLT)], robot_moving_itself=True) == []


# Recordings from the robot (sprint B spike). imu_rest.csv: nothing for 10 s,
# three knocks on the table, three on the head, then lifted and put down.
# imu_self_motion.csv: the app running, a sneeze requested around 14 s, then
# breathing alone from 20 s.


def test_nothing_happens_before_the_knocks():
    times = bump_times(load_accelerometer("imu_rest.csv"))

    assert [t for t in times if t < 10.0] == []


def test_finds_the_firm_knocks():
    times = bump_times(load_accelerometer("imu_rest.csv"))

    # Of the six knocks, two were too light to stand out from breathing.
    assert len([t for t in times if 10.0 <= t < 30.0]) == 4


def test_breathing_alone_is_no_bump():
    times = bump_times(load_accelerometer("imu_self_motion.csv"))

    assert [t for t in times if t >= 20.0] == []


def test_a_sneeze_reads_as_bumps_to_the_detector_alone():
    # Without robot_moving_itself, the robot's own sneeze shakes it like a knock.
    times = bump_times(load_accelerometer("imu_self_motion.csv"))

    assert [t for t in times if 13.5 <= t < 19.5] != []

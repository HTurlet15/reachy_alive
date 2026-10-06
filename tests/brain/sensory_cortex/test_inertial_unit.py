"""Unit tests for BumpDetector and InertialUnitSense.

BumpDetector is tested on made-up readings and on recordings from the robot.
"""

import csv
import logging
import time
from pathlib import Path
from unittest.mock import MagicMock

from reachy_alive.brain.sensory_cortex.inertial_unit import BumpDetector, InertialUnitSense
from reachy_alive.shared_state import SharedState

DATA = Path(__file__).parent / "data"


def load_accelerometer(name: str) -> list[tuple[float, tuple[float, float, float]]]:
    """Load (t, (ax, ay, az)) readings from a recording in tests' data folder."""
    with open(DATA / name) as f:
        return [
            (float(r["t_s"]), (float(r["ax"]), float(r["ay"]), float(r["az"])))
            for r in csv.DictReader(f)
        ]


def bump_times(readings) -> list[float]:
    """Feed readings to a fresh BumpDetector and return when it found bumps."""
    detector = BumpDetector()
    return [t for t, accelerometer in readings if detector.update(t, accelerometer)]


def test_gravity_alone_is_no_bump():
    assert not BumpDetector().update(0.0, (0.0, 0.0, 9.81))


def test_a_tilted_head_is_no_bump():
    # Tilting the head moves gravity to another axis without changing its norm.
    assert not BumpDetector().update(0.0, (9.81, 0.0, 0.0))


def test_a_jolt_is_a_bump():
    assert BumpDetector().update(0.0, (0.0, 0.0, 15.0))


def test_a_dip_below_gravity_is_a_bump_too():
    assert BumpDetector().update(0.0, (0.0, 0.0, 4.0))


def test_a_bump_is_reported_once_while_the_head_rings():
    detector = BumpDetector(refractory_s=0.3)

    assert detector.update(0.00, (0.0, 0.0, 15.0))
    assert not detector.update(0.02, (0.0, 0.0, 4.0))
    assert not detector.update(0.20, (0.0, 0.0, 14.0))


def test_a_second_bump_after_the_refractory_period_counts():
    detector = BumpDetector(refractory_s=0.3)
    detector.update(0.0, (0.0, 0.0, 15.0))

    assert detector.update(0.5, (0.0, 0.0, 15.0))


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
    times = bump_times(load_accelerometer("imu_self_motion.csv"))

    assert [t for t in times if 13.5 <= t < 19.5] != []


# InertialUnitSense, with a fake robot whose inertial unit always reads the same.

JOLT = {"accelerometer": [0.0, 0.0, 15.0]}
STILL = {"accelerometer": [0.0, 0.0, 9.81]}


def make_sense(imu: dict | None) -> tuple[InertialUnitSense, SharedState]:
    """Build a sense on a fake robot, long after the last move ended."""
    reachy_mini = MagicMock()
    reachy_mini.imu = imu
    state = SharedState()
    state.last_activity_at = time.monotonic() - 50.0
    return InertialUnitSense(reachy_mini, state), state


def test_sense_records_a_bump():
    sense, state = make_sense(JOLT)
    now = time.monotonic()

    sense.step(now)

    assert state.last_bump_at() == now


def test_sense_records_nothing_while_still():
    sense, state = make_sense(STILL)

    sense.step(time.monotonic())

    assert state.last_bump_at() is None


def test_sense_ignores_bumps_while_a_move_plays():
    sense, state = make_sense(JOLT)
    state.set_move_playing(True)

    sense.step(time.monotonic())

    assert state.last_bump_at() is None


def test_sense_ignores_bumps_right_after_a_move():
    sense, state = make_sense(JOLT)
    state.mark_activity()  # a move just ended

    sense.step(time.monotonic())

    assert state.last_bump_at() is None


def test_sense_without_an_inertial_unit_says_so_once(caplog):
    sense, state = make_sense(None)

    with caplog.at_level(logging.INFO):
        sense.step(1.0)
        sense.step(2.0)

    assert state.last_bump_at() is None
    assert caplog.text.count("No inertial unit") == 1
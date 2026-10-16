"""Unit tests for Detector, the contract every detector follows, and the tools detectors share."""

import math
from dataclasses import dataclass

import pytest

from reachy_alive.brain.sensory_cortex.detector import Background, Detector, SchmittTrigger


@dataclass(frozen=True)
class MadeUpFeatures:
    """The least features a detector can read."""

    t: float
    robot_moving_itself: bool


STILL = MadeUpFeatures(t=1.0, robot_moving_itself=False)
MOVING = MadeUpFeatures(t=1.0, robot_moving_itself=True)


class MinimalDetector(Detector):
    """A detector that writes only what it must: _detect. It keeps all the features it reads."""

    def __init__(self, facts) -> None:
        super().__init__(facts)
        self.detected = []

    def _detect(self, features: MadeUpFeatures) -> None:
        self.detected.append(features)


def test_a_detector_reads_the_features_the_robot_did_not_disturb():
    detector = MinimalDetector(facts="the facts")

    detector.update(STILL)

    assert detector.detected == [STILL]


def test_features_disturbed_by_the_robot_are_ignored_by_default():
    detector = MinimalDetector(facts="the facts")

    detector.update(MOVING)

    assert detector.detected == []


def test_a_detector_can_follow_the_features_disturbed_by_the_robot():
    class FollowingDetector(MinimalDetector):
        def _while_robot_moves(self, features: MadeUpFeatures) -> None:
            self.followed = features

    detector = FollowingDetector(facts="the facts")

    detector.update(MOVING)

    assert detector.followed == MOVING
    assert detector.detected == []


def test_a_detector_without_detect_cannot_be_built():
    class ForgetfulDetector(Detector):
        pass

    with pytest.raises(TypeError):
        ForgetfulDetector(facts="the facts")


# SchmittTrigger, with the antennas' thresholds: on at 5, off under 3


def make_trigger() -> SchmittTrigger:
    return SchmittTrigger(on_threshold=5.0, off_threshold=3.0)


def test_it_starts_off():
    trigger = make_trigger()

    assert trigger.is_on() is False
    assert trigger.on_since is None


def test_it_turns_on_once_the_value_reaches_the_on_threshold():
    trigger = make_trigger()

    trigger.update(1.0, 5.0)

    assert trigger.on_since == 1.0


def test_it_stays_on_between_the_thresholds_since_it_turned_on():
    trigger = make_trigger()
    trigger.update(1.0, 6.0)

    trigger.update(2.0, 4.0)

    assert trigger.on_since == 1.0


def test_it_turns_off_under_the_off_threshold():
    trigger = make_trigger()
    trigger.update(1.0, 6.0)

    trigger.update(2.0, 2.0)

    assert trigger.is_on() is False


def test_a_value_between_the_thresholds_does_not_turn_it_on():
    trigger = make_trigger()

    trigger.update(1.0, 4.0)

    assert trigger.is_on() is False


def test_only_a_trigger_that_is_off_would_turn_on():
    trigger = make_trigger()
    assert trigger.would_turn_on(6.0) is True

    trigger.update(1.0, 6.0)

    assert trigger.would_turn_on(7.0) is False  # already on: nothing starts


def test_asking_does_not_change_it():
    trigger = make_trigger()

    trigger.would_turn_on(6.0)

    assert trigger.is_on() is False


def test_the_off_threshold_cannot_be_above_the_on_threshold():
    with pytest.raises(ValueError):
        SchmittTrigger(on_threshold=3.0, off_threshold=5.0)


# Background, with a time constant of 2 s


def test_the_first_value_followed_is_the_background():
    background = Background(time_constant_s=2.0)

    background.follow(0.0, -60.0)

    assert background.height_of(-60.0) == 0.0


def test_after_one_time_constant_it_has_covered_63_percent_of_the_way():
    background = Background(time_constant_s=2.0)
    background.follow(0.0, 0.0)

    background.follow(2.0, 100.0)

    level = 100.0 - background.height_of(100.0)
    assert math.isclose(level, 100.0 * (1 - math.exp(-1)))  # about 63


def test_two_steps_of_1_s_cover_as_much_as_one_step_of_2_s():
    # What counts is the time elapsed, not how many values it was given.
    in_two_steps = Background(time_constant_s=2.0)
    in_two_steps.follow(0.0, 0.0)
    in_two_steps.follow(1.0, 100.0)
    in_two_steps.follow(2.0, 100.0)
    in_one_step = Background(time_constant_s=2.0)
    in_one_step.follow(0.0, 0.0)
    in_one_step.follow(2.0, 100.0)

    assert math.isclose(in_two_steps.height_of(0.0), in_one_step.height_of(0.0))


def test_nothing_stands_out_before_the_background_has_a_level():
    assert Background(time_constant_s=2.0).height_of(-20.0) == 0.0


def test_the_height_of_a_value_is_measured_from_the_background():
    background = Background(time_constant_s=2.0)
    background.follow(0.0, -60.0)

    assert background.height_of(-20.0) == 40.0
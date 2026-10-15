"""Unit tests for Detector, the contract every detector follows."""

from dataclasses import dataclass

import pytest

from reachy_alive.brain.sensory_cortex.detector import Detector


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
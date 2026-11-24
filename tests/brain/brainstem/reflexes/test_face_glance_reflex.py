"""Unit tests for FaceGlanceReflex: one glance per face that appears."""

import math

import numpy as np
import pytest

from reachy_alive.brain.brainstem.reflexes.face_glance_reflex import FaceGlanceReflex
from reachy_alive.brain.sensory_cortex.vision.vision_features import SeenFace
from reachy_alive.shared_state import CommandedPose, SharedState

FACE_ON_THE_LEFT = SeenFace(x=-0.5, y=0.0, distance_m=1.0, yaw_rad=math.radians(15))


def head_turned_by(yaw_rad):
    """A head pose turned around the vertical axis, as the MotionGenerator sends it."""
    cos, sin = math.cos(yaw_rad), math.sin(yaw_rad)
    return np.array([[cos, -sin, 0, 0], [sin, cos, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])


@pytest.fixture
def state():
    return SharedState()


def test_without_a_face_it_proposes_nothing(state):
    assert FaceGlanceReflex(state).propose(now=1.0) is None


def test_it_looks_at_a_face_that_appears(state):
    state.vision.record_face_appeared(1.0, FACE_ON_THE_LEFT)

    proposal = FaceGlanceReflex(state).propose(now=1.1)

    assert proposal.move_to_start is None
    assert proposal.direction.yaw_rad == pytest.approx(math.radians(15))


def test_it_looks_once_while_the_face_stays(state):
    reflex = FaceGlanceReflex(state)
    state.vision.record_face_appeared(1.0, FACE_ON_THE_LEFT)

    reflex.propose(now=1.1)

    assert reflex.propose(now=1.2) is None


def test_it_looks_again_at_a_face_that_comes_back(state):
    reflex = FaceGlanceReflex(state)
    state.vision.record_face_appeared(1.0, FACE_ON_THE_LEFT)
    reflex.propose(now=1.1)
    state.vision.record_face_lost(2.0)
    state.vision.record_face_appeared(3.0, FACE_ON_THE_LEFT)

    assert reflex.propose(now=3.1) is not None


def test_the_angle_adds_to_where_the_head_already_points(state):
    state.record_commanded_pose(
        CommandedPose(at=0.9, head=head_turned_by(math.radians(30)), antennas=np.zeros(2))
    )
    state.vision.record_face_appeared(1.0, FACE_ON_THE_LEFT)

    proposal = FaceGlanceReflex(state).propose(now=1.1)

    assert proposal.direction.yaw_rad == pytest.approx(math.radians(45))

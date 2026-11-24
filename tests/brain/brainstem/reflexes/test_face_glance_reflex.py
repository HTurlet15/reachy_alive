"""Unit tests for FaceGlanceReflex: one glance per face that appears, then letting go."""

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
    reflex.propose(now=2.1)  # lets go
    state.vision.record_face_appeared(3.0, FACE_ON_THE_LEFT)

    proposal = reflex.propose(now=3.1)

    assert proposal.direction.yaw_rad == pytest.approx(math.radians(15))


def test_the_angle_adds_to_where_the_head_already_points(state):
    state.record_commanded_pose(
        CommandedPose(at=0.9, head=head_turned_by(math.radians(30)), antennas=np.zeros(2))
    )
    state.vision.record_face_appeared(1.0, FACE_ON_THE_LEFT)

    proposal = FaceGlanceReflex(state).propose(now=1.1)

    assert proposal.direction.yaw_rad == pytest.approx(math.radians(45))


# Letting go


def sent_with_body_at(state, body_yaw_rad):
    """Record a last pose sent with the body turned by body_yaw_rad, head over it."""
    state.record_commanded_pose(
        CommandedPose(
            at=0.9, head=head_turned_by(body_yaw_rad), antennas=np.zeros(2), body_yaw=body_yaw_rad
        )
    )


def looking_at_a_face(state):
    """A reflex that has just looked at a face that appeared at 1.0 s."""
    reflex = FaceGlanceReflex(state)
    state.vision.record_face_appeared(1.0, FACE_ON_THE_LEFT)
    reflex.propose(now=1.1)
    return reflex


def test_it_keeps_looking_while_interest_lasts(state):
    reflex = looking_at_a_face(state)

    assert reflex.propose(now=1.0 + FaceGlanceReflex.HOLD_S - 0.1) is None


def test_once_interest_fades_the_head_comes_back_over_the_body(state):
    reflex = looking_at_a_face(state)
    sent_with_body_at(state, math.radians(10))

    proposal = reflex.propose(now=1.0 + FaceGlanceReflex.HOLD_S)

    assert proposal.direction.yaw_rad == pytest.approx(math.radians(10))


def test_it_lets_go_as_soon_as_the_face_leaves(state):
    reflex = looking_at_a_face(state)
    state.vision.record_face_lost(1.5)

    assert reflex.propose(now=1.6) is not None


def test_after_letting_go_it_does_not_look_again_at_the_same_face(state):
    reflex = looking_at_a_face(state)
    reflex.propose(now=1.0 + FaceGlanceReflex.HOLD_S)  # lets go; the face stays

    assert reflex.propose(now=1.0 + FaceGlanceReflex.HOLD_S + 0.1) is None

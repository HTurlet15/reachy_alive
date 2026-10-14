"""Tests for FacePresenceDetector, fed with the made-up features of 5 images per second."""

from reachy_alive.brain.sensory_cortex.vision.face_presence_detector import FacePresenceDetector
from reachy_alive.brain.sensory_cortex.vision.vision_features import SeenFace, VisionFeatures
from reachy_alive.shared_state import VisionFacts

FRAME_PERIOD_S = 0.2
NEAR = SeenFace(x=0.0, y=0.0, distance_m=1.0)
NEAR_MOVED = SeenFace(x=0.4, y=0.0, distance_m=1.0)
NEARER = SeenFace(x=-0.5, y=0.0, distance_m=0.6)
TOO_FAR = SeenFace(x=0.0, y=0.0, distance_m=FacePresenceDetector.MAX_FACE_DISTANCE_M + 0.5)


def make_detector() -> tuple[FacePresenceDetector, VisionFacts]:
    facts = VisionFacts()
    return FacePresenceDetector(facts), facts


def show(detector: FacePresenceDetector, start_s: float, duration_s: float, *faces: SeenFace,
         robot_moving_itself: bool = False) -> float:
    """Feed one image's features every FRAME_PERIOD_S for `duration_s`, and return when it stopped."""
    t = start_s
    while t < start_s + duration_s - 1e-9:
        detector.update(VisionFeatures(t=t, faces=faces, robot_moving_itself=robot_moving_itself))
        t = round(t + FRAME_PERIOD_S, 6)
    return t


def test_no_face_seen_at_first():
    _, facts = make_detector()
    assert facts.face_seen_since() is None


def test_a_face_glimpsed_does_not_appear():
    detector, facts = make_detector()
    show(detector, 0.0, 0.2, NEAR)  # one stray image: a false positive
    show(detector, 0.2, 2.0)
    assert facts.face_seen_since() is None


def test_a_face_that_stays_appears_since_it_was_first_seen():
    detector, facts = make_detector()
    show(detector, 10.0, 1.0, NEAR)
    assert facts.face_seen_since() == 10.0
    assert facts.main_face() == NEAR


def test_a_face_seen_with_gaps_does_not_appear():
    detector, facts = make_detector()
    for start_s in (0.0, 0.4, 0.8, 1.2):  # seen, missed, seen, missed…
        show(detector, start_s, 0.2, NEAR)
        show(detector, start_s + 0.2, 0.2)
    assert facts.face_seen_since() is None


def test_a_face_missed_briefly_stays_in_view():
    detector, facts = make_detector()
    t = show(detector, 0.0, 1.0, NEAR)
    t = show(detector, t, 0.6)  # the detector misses it: a false negative
    show(detector, t, 0.4, NEAR_MOVED)
    assert facts.face_seen_since() == 0.0
    assert facts.last_face_lost_at() is None
    assert facts.main_face() == NEAR_MOVED


def test_a_face_gone_for_long_is_lost_when_it_was_last_seen():
    detector, facts = make_detector()
    t = show(detector, 0.0, 1.0, NEAR)
    show(detector, t, 2.0)
    assert facts.face_seen_since() is None
    assert facts.main_face() is None
    assert facts.last_face_lost_at() == t - FRAME_PERIOD_S


def test_a_face_too_far_is_ignored():
    detector, facts = make_detector()
    show(detector, 0.0, 2.0, TOO_FAR)
    assert facts.face_seen_since() is None


def test_the_nearest_face_is_the_main_one():
    detector, facts = make_detector()
    show(detector, 0.0, 1.0, NEARER, NEAR)  # the sense sorts faces nearest first
    assert facts.main_face() == NEARER


def test_images_taken_while_the_robot_moves_itself_are_ignored():
    detector, facts = make_detector()
    t = show(detector, 0.0, 1.0, NEAR)
    show(detector, t, 2.0, robot_moving_itself=True)  # the camera swings: no face in view
    assert facts.face_seen_since() == 0.0


def test_a_face_still_there_after_a_move_is_not_lost_at_once():
    detector, facts = make_detector()
    t = show(detector, 0.0, 1.0, NEAR)
    t = show(detector, t, 10.0, robot_moving_itself=True)  # a long move
    t = show(detector, t, 0.2)  # the first image after the move misses the face
    show(detector, t, 0.4, NEAR)
    assert facts.face_seen_since() == 0.0
    assert facts.last_face_lost_at() is None


def test_a_face_gone_during_a_move_is_lost_a_while_after_it():
    detector, facts = make_detector()
    t = show(detector, 0.0, 1.0, NEAR)
    t = show(detector, t, 10.0, robot_moving_itself=True)
    show(detector, t, 2.0)  # nobody there once the move is over
    assert facts.face_seen_since() is None
    assert facts.last_face_lost_at() == 0.8
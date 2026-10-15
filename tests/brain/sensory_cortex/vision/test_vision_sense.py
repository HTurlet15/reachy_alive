"""Unit tests for the vision sense: one face described, then whole images from a made-up camera.

Pixel coordinates start at the image's top-left corner: x grows to the right,
y grows downward. The analysed image is 320x180, the size the sense shrinks
the camera's 1280x720 images to.
"""

import math
from types import SimpleNamespace

import numpy as np
from reachy_mini.vision.face_detector import Face

from reachy_alive.brain.sensory_cortex.vision.vision_features import SeenFace
from reachy_alive.brain.sensory_cortex.vision.vision_sense import VisionSense
from reachy_alive.shared_state import SharedState

IMAGE_WIDTH_PX = 320
IMAGE_HEIGHT_PX = 180
CENTER_X_PX = IMAGE_WIDTH_PX / 2
CENTER_Y_PX = IMAGE_HEIGHT_PX / 2
FOCAL_PX = 140.0
# Pinhole camera: at 1 m, an average face spans its width in meters times the focal length.
FACE_AT_ONE_METER_PX = FOCAL_PX * VisionSense.AVERAGE_FACE_WIDTH_M

CAMERA_WIDTH_PX = 1280
CAMERA_HEIGHT_PX = 720
CAMERA_FOCAL_PX = 4 * FOCAL_PX  # shrunk 4 times, the focal length is FOCAL_PX
CAMERA_MATRIX = np.array([
    [CAMERA_FOCAL_PX, 0.0, CAMERA_WIDTH_PX / 2],
    [0.0, CAMERA_FOCAL_PX, CAMERA_HEIGHT_PX / 2],
    [0.0, 0.0, 1.0],
])
CAMERA_IMAGE = np.zeros((CAMERA_HEIGHT_PX, CAMERA_WIDTH_PX, 3), dtype=np.uint8)


def face_centered_at(x_px: float, y_px: float, width_px: float = 20.0) -> Face:
    """Return a square face box centered on (x_px, y_px).

    The SDK's face finder (YuNet) describes a box by its top-left corner and its
    size; the eyes and nose don't matter to the features.
    """
    return Face(
        bbox=(x_px - width_px / 2, y_px - width_px / 2, width_px, width_px),
        right_eye=(0.0, 0.0),
        left_eye=(0.0, 0.0),
        nose=(0.0, 0.0),
    )


def describe(face: Face) -> SeenFace:
    """Describe a face found in the analysed image."""
    return VisionSense.seen_face(face, IMAGE_WIDTH_PX, IMAGE_HEIGHT_PX, FOCAL_PX)


# One face


def test_a_face_at_the_center_of_the_image_is_at_zero_zero():
    face = describe(face_centered_at(x_px=CENTER_X_PX, y_px=CENTER_Y_PX))

    assert (face.x, face.y) == (0.0, 0.0)


def test_a_face_on_the_left_edge_is_at_minus_one():
    face = describe(face_centered_at(x_px=0, y_px=CENTER_Y_PX))

    assert face.x == -1.0


def test_a_face_on_the_right_edge_is_at_one():
    face = describe(face_centered_at(x_px=IMAGE_WIDTH_PX, y_px=CENTER_Y_PX))

    assert face.x == 1.0


def test_a_face_on_the_bottom_edge_is_at_one():
    face = describe(face_centered_at(x_px=CENTER_X_PX, y_px=IMAGE_HEIGHT_PX))

    assert face.y == 1.0


def test_a_face_box_focal_times_face_width_wide_is_one_meter_away():
    face = describe(
        face_centered_at(CENTER_X_PX, CENTER_Y_PX, width_px=FACE_AT_ONE_METER_PX)
    )

    assert math.isclose(face.distance_m, 1.0)


def test_a_face_half_as_wide_is_twice_as_far():
    near = describe(face_centered_at(CENTER_X_PX, CENTER_Y_PX, width_px=40))
    far = describe(face_centered_at(CENTER_X_PX, CENTER_Y_PX, width_px=20))

    assert math.isclose(far.distance_m, 2 * near.distance_m)


# Whole images, from a made-up camera and face detector


class FakeFaceFinder:
    """Finds the faces it is given, and remembers the size of the image it was shown."""

    def __init__(self, faces: list[Face]) -> None:
        self.faces = faces
        self.image_shape: tuple[int, ...] | None = None

    def detect(self, image: np.ndarray) -> list[Face]:
        self.image_shape = image.shape
        return self.faces


def make_sense(image=CAMERA_IMAGE, faces=(), has_camera=True):
    """Build a vision sense on a made-up robot."""
    camera = SimpleNamespace(K=CAMERA_MATRIX) if has_camera else None
    reachy_mini = SimpleNamespace(media=SimpleNamespace(camera=camera, get_frame=lambda: image))
    shared_state = SharedState()
    face_finder = FakeFaceFinder(list(faces))
    return VisionSense(reachy_mini, shared_state, face_finder), shared_state, face_finder


def test_the_features_are_timed_by_the_reading():
    sense, _, _ = make_sense()

    features = sense.read_once(now=12.0)

    assert features.t == 12.0


def test_faces_are_found_in_a_shrunk_image():
    sense, _, face_finder = make_sense()

    sense.read_once(now=0.0)

    assert face_finder.image_shape == (IMAGE_HEIGHT_PX, IMAGE_WIDTH_PX, 3)


def test_the_focal_length_shrinks_with_the_image():
    face = face_centered_at(CENTER_X_PX, CENTER_Y_PX, width_px=FACE_AT_ONE_METER_PX)
    sense, _, _ = make_sense(faces=[face])

    features = sense.read_once(now=0.0)

    assert math.isclose(features.faces[0].distance_m, 1.0)


def test_faces_come_nearest_first():
    far = face_centered_at(CENTER_X_PX, CENTER_Y_PX, width_px=10)
    near = face_centered_at(CENTER_X_PX, CENTER_Y_PX, width_px=40)
    sense, _, _ = make_sense(faces=[far, near])

    features = sense.read_once(now=0.0)

    distances_m = [face.distance_m for face in features.faces]
    assert distances_m == sorted(distances_m)


def test_the_features_say_when_the_robot_moves_itself():
    sense, shared_state, _ = make_sense()
    shared_state.set_move_playing(True)

    features = sense.read_once(now=0.0)

    assert features.robot_moving_itself is True


def test_no_image_yet_gives_no_features():
    sense, _, _ = make_sense(image=None)

    assert sense.read_once(now=0.0) is None


def test_without_a_camera_the_sense_is_unavailable():
    sense, _, _ = make_sense(has_camera=False)

    assert sense.is_available() is False
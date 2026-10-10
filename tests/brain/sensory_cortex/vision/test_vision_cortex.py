"""Unit tests for the vision cortex's features, on faces placed by hand.

Pixel coordinates start at the image's top-left corner: x grows to the right,
y grows downward. The image is 320x180, the size the cortex analyses.
"""

import math

from reachy_mini.vision.face_detector import Face

from reachy_alive.brain.sensory_cortex.vision.vision_cortex import (
    AVERAGE_FACE_WIDTH_M,
    SeenFace,
    seen_face,
)

IMAGE_WIDTH_PX = 320
IMAGE_HEIGHT_PX = 180
CENTER_X_PX = IMAGE_WIDTH_PX / 2
CENTER_Y_PX = IMAGE_HEIGHT_PX / 2
FOCAL_PX = 140.0


def face_centered_at(x_px: float, y_px: float, width_px: float = 20.0) -> Face:
    """Return a square face box centered on (x_px, y_px).

    The SDK's face detector describes a box by its top-left corner and its
    size; the eyes and nose don't matter to the features.
    """
    return Face(
        bbox=(x_px - width_px / 2, y_px - width_px / 2, width_px, width_px),
        right_eye=(0.0, 0.0),
        left_eye=(0.0, 0.0),
        nose=(0.0, 0.0),
    )


def describe(face: Face) -> SeenFace:
    """Describe a face found in the test image."""
    return seen_face(face, IMAGE_WIDTH_PX, IMAGE_HEIGHT_PX, FOCAL_PX)


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
    # Pinhole camera: at 1 m, a 0.15 m wide face spans 140 x 0.15 = 21 pixels.
    face = describe(
        face_centered_at(CENTER_X_PX, CENTER_Y_PX, width_px=FOCAL_PX * AVERAGE_FACE_WIDTH_M)
    )

    assert math.isclose(face.distance_m, 1.0)


def test_a_face_half_as_wide_is_twice_as_far():
    near = describe(face_centered_at(CENTER_X_PX, CENTER_Y_PX, width_px=40))
    far = describe(face_centered_at(CENTER_X_PX, CENTER_Y_PX, width_px=20))

    assert math.isclose(far.distance_m, 2 * near.distance_m)
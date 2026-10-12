"""Vision: what the camera sees, described as features, one frame at a time."""

from dataclasses import dataclass

from reachy_mini.vision.face_detector import Face


@dataclass(frozen=True)
class SeenFace:
    """A face in the camera's view.

    Attributes:
        x: Horizontal position, from -1 at the left edge of the view to 1 at
            the right edge, as the robot sees it.
        y: Vertical position, from -1 at the top edge to 1 at the bottom edge.
        distance_m: Estimated distance from the camera, in meters.
    """

    x: float
    y: float
    distance_m: float


@dataclass(frozen=True)
class VisionFrame:
    """What the camera saw in one image: the features every vision detector reads.

    Attributes:
        t: When the image was taken, in seconds, on time.monotonic()'s clock.
        faces: Every face in view, nearest first.
        robot_moving_itself: Whether the robot was moving itself, so the view
            itself was moving.
    """

    t: float
    faces: tuple[SeenFace, ...]
    robot_moving_itself: bool


# Width of an average face, as the face detector boxes it: wider than the face
# itself, ears and hair included. Measured with a tape, 0.5 to 2.5 m. Faces vary
# by about 20%, and so does the distance estimated from it.
AVERAGE_FACE_WIDTH_M = 0.195


def seen_face(face: Face, image_width_px: int, image_height_px: int, focal_px: float) -> SeenFace:
    """Describe a face found by the detector: where it is, and how far.

    Args:
        face: A face found by the SDK's face detector, in pixels.
        image_width_px: Width of the image the face was found in.
        image_height_px: Height of that image.
        focal_px: The camera's focal length, in pixels of that image.
    """
    left_px, top_px, width_px, height_px = face.bbox
    center_x_px = left_px + width_px / 2
    center_y_px = top_px + height_px / 2
    return SeenFace(
        x=2 * center_x_px / image_width_px - 1,
        y=2 * center_y_px / image_height_px - 1,
        # A pinhole camera: an object's size in the image shrinks with its distance.
        distance_m=focal_px * AVERAGE_FACE_WIDTH_M / width_px,
    )
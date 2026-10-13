"""The vision messages: what the vision sense hands to the vision detectors.

The catalogue for whoever writes a vision detector: everything it can read.
"""

from dataclasses import dataclass


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
        robot_moving_itself: Whether the robot was playing a move, so the view
            itself was moving.
    """

    t: float
    faces: tuple[SeenFace, ...]
    robot_moving_itself: bool

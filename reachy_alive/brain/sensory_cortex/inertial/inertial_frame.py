"""The inertial messages: what the inertial sense hands to the inertial detectors."""

from dataclasses import dataclass


@dataclass(frozen=True)
class InertialFrame:
    """What the inertial unit felt in one reading: what every inertial detector reads.

    Attributes:
        t: When the reading was taken, in seconds, on time.monotonic()'s clock.
        accelerometer: (x, y, z) acceleration, in m/s², gravity included.
        robot_moving_itself: Whether a move was playing or had just ended, so
            the robot felt its own motion.
    """

    t: float
    accelerometer: tuple[float, float, float]
    robot_moving_itself: bool

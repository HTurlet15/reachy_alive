"""The inertial features: what the inertial sense felt in one reading."""

from dataclasses import dataclass


@dataclass(frozen=True)
class InertialFeatures:
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
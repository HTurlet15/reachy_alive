"""The inertial features: what the inertial sense felt in one reading."""

from dataclasses import dataclass


@dataclass(frozen=True)
class InertialFeatures:
    """What the inertial unit felt in one reading: what every inertial detector reads.

    Attributes:
        perceived_at: When the sense perceived this, in seconds, on
            time.monotonic()'s clock: every fact a detector records from it
            is dated with it.
        accelerometer: (x, y, z) acceleration, in m/s², gravity included.
        robot_moving_itself: Whether a move was playing or had just ended, so
            the robot felt its own motion.
    """

    perceived_at: float
    accelerometer: tuple[float, float, float]
    robot_moving_itself: bool

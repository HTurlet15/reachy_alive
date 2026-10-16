"""The touch features: what the touch sense felt in one reading."""

from dataclasses import dataclass

# The antennas in the SDK's order, on the real robot.
ANTENNA_SIDES = ("right", "left")


@dataclass(frozen=True)
class TouchFeatures:
    """Where the antennas were sent, and where they are: what every touch detector reads.

    Attributes:
        perceived_at: When the sense perceived this, in seconds, on
            time.monotonic()'s clock: every fact a detector records from it
            is dated with it.
        targets_rad: Where RobotController last sent each antenna, in
            ANTENNA_SIDES order, in radians.
        measured_rad: Where each antenna is, measured, in the same order.
        robot_moving_itself: Whether a move was playing or had just ended:
            the antennas then follow targets RobotController didn't send.
    """

    perceived_at: float
    targets_rad: tuple[float, float]
    measured_rad: tuple[float, float]
    robot_moving_itself: bool

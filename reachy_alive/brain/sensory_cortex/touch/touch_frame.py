"""The touch messages: what the touch sense hands to the touch detectors."""

from dataclasses import dataclass

# The antennas in the SDK's order, on the real robot.
ANTENNA_SIDES = ("right", "left")


@dataclass(frozen=True)
class TouchFrame:
    """Where the antennas were sent, and where they are: what every touch detector reads.

    Attributes:
        t: When the antennas were read, in seconds, on time.monotonic()'s clock.
        targets_rad: Where RobotController last sent each antenna, in
            ANTENNA_SIDES order, in radians.
        measured_rad: Where each antenna is, measured, in the same order.
        robot_moving_itself: Whether a move was playing or had just ended:
            the antennas then follow targets RobotController didn't send.
    """

    t: float
    targets_rad: tuple[float, float]
    measured_rad: tuple[float, float]
    robot_moving_itself: bool

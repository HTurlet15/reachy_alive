"""The hearing features: what the hearing sense heard in one 20 ms stretch of sound."""

from dataclasses import dataclass


@dataclass(frozen=True)
class HearingFeatures:
    """How loud one 20 ms stretch of sound is: what every hearing detector reads.

    Attributes:
        perceived_at: When the sense perceived this, in seconds, on
            time.monotonic()'s clock: every fact a detector records from it
            is dated with it.
        time_listened_s: How long the sense has listened, by the end of the
            stretch, in seconds: the sound's own clock. It starts at 0 and
            only goes up, 20 ms per stretch, even when chunks of sound arrive
            late or bunched up. Detectors that follow the sound over time
            follow this clock.
        level_dbfs: How loud the stretch is. 0 dBFS is the loudest sound the
            microphones can report.
        robot_moving_itself: Whether a move was playing or had just ended:
            the robot then hears its own motors.
    """

    perceived_at: float
    time_listened_s: float
    level_dbfs: float
    robot_moving_itself: bool

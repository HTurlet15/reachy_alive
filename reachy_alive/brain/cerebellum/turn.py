"""A turn from one direction to another: slow, fast, then slow."""

from dataclasses import dataclass

from reachy_mini.utils.interpolation import InterpolationTechnique, time_trajectory


@dataclass(frozen=True)
class Turn:
    """A turn toward a direction, easing in and out along the SDK's min-jerk curve.

    Attributes:
        from_rad: Where the turn starts, left of the robot's front, in radians.
        to_rad: Where it ends.
        started_at: When it started: a time.monotonic() reading.
        duration_s: How long it takes; 0 turns at once.
    """

    from_rad: float
    to_rad: float
    started_at: float
    duration_s: float

    def direction_at(self, now: float) -> float:
        """Return where the turn is at now; once it is over, where it ends."""
        if self.duration_s <= 0.0:
            return self.to_rad
        # time_trajectory refuses a progress above 1: a tick rarely lands on the end.
        progress = min((now - self.started_at) / self.duration_s, 1.0)
        eased = time_trajectory(progress, InterpolationTechnique.MIN_JERK)
        return self.from_rad + eased * (self.to_rad - self.from_rad)

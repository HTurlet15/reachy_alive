"""The touch sense: where the antennas are, against where they were sent, 50 times a second."""

import math

from reachy_mini import ReachyMini

from reachy_alive.brain.sensory_cortex.touch.touch_frame import TouchFrame
from reachy_alive.shared_state import SharedState


class TouchSense:
    """Reads the antennas and describes each reading as a TouchFrame.

    Never drives the robot, and knows nothing of the detectors: SenseManager
    calls it and hands its frames on.
    """

    # RobotController sends new targets 50 times a second.
    PERIOD_S = 0.02
    # The antennas still settle this long after the robot last moved itself.
    SETTLE_AFTER_MOVE_S = 0.5

    def __init__(self, reachy_mini: ReachyMini, shared_state: SharedState) -> None:
        """Keep what the sense reads from.

        Args:
            reachy_mini: Connected robot instance, only read.
            shared_state: Where the sense learns where the antennas were sent,
                and whether the robot is moving itself.
        """
        self._reachy_mini = reachy_mini
        self._shared_state = shared_state
        self._last_seen_moving_at = -math.inf

    def is_available(self) -> bool:
        """Return True: every Reachy Mini has antennas."""
        return True

    def read_once(self, now: float) -> TouchFrame | None:
        """Describe where the antennas are, or return None if none was sent anywhere yet.

        Args:
            now: Time of the reading, in seconds, on time.monotonic()'s clock.
        """
        commanded_pose = self._shared_state.last_commanded_pose()
        if commanded_pose is None:
            return None  # nothing sent yet: where the antennas should be is unknown
        if self._shared_state.is_move_playing():
            self._last_seen_moving_at = now
        return TouchFrame(
            t=now,
            targets_rad=tuple(commanded_pose.antennas),
            measured_rad=tuple(self._reachy_mini.get_present_antenna_joint_positions()),
            robot_moving_itself=now - self._last_seen_moving_at < self.SETTLE_AFTER_MOVE_S,
        )

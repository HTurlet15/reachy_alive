"""The touch sense: where the antennas are, against where they were sent, 50 times a second."""

from reachy_alive.brain.sensory_cortex.sense import Sense
from reachy_alive.brain.sensory_cortex.touch.touch_features import TouchFeatures


class TouchSense(Sense):
    """Reads the antennas and describes each reading by its TouchFeatures.

    Where the antennas were sent comes from SharedState: the last pose
    RobotController sent.
    """

    # RobotController sends new targets 50 times a second.
    PERIOD_S = 0.02

    def _perceive(self, perceived_at: float, robot_moving_itself: bool) -> TouchFeatures | None:
        """Describe where the antennas are, or return None if none was sent anywhere yet."""
        commanded_pose = self._shared_state.last_commanded_pose()
        if commanded_pose is None:
            return None  # nothing sent yet: where the antennas should be is unknown
        return TouchFeatures(
            perceived_at=perceived_at,
            targets_rad=tuple(commanded_pose.antennas),
            measured_rad=tuple(self._reachy_mini.get_present_antenna_joint_positions()),
            robot_moving_itself=robot_moving_itself,
        )

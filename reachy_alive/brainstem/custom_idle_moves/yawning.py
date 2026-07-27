from reachy_mini import ReachyMini
from reachy_mini.utils import create_head_pose

from reachy_alive.move import Move


class Yawning(Move):
    """Plays a hand-made yawn: head rises, antennas lower, hold, release."""

    RISE_PITCH_DEG = -20.0  
    ANTENNAS_LOWERED_RAD = -1.0
    RISE_DURATION_S = 1.5
    HOLD_DURATION_S = 0.8
    RELEASE_DURATION_S = 1.0

    def trigger(self, reachy_mini: ReachyMini) -> None:
        # TODO: play a yawning sound here once a .wav asset is chosen,
        # e.g. reachy_mini.media.play_sound("yawn.wav"). Not implemented
        # yet -- sound plumbing was deliberately deferred (see main.py
        # history), reintroduce it here directly rather than through
        # settings_app, since this call doesn't need any external trigger.

        rise_pose = create_head_pose(pitch=self.RISE_PITCH_DEG, degrees=True)
        reachy_mini.goto_target(
            head=rise_pose,
            antennas=[self.ANTENNAS_LOWERED_RAD, -self.ANTENNAS_LOWERED_RAD],
            duration=self.RISE_DURATION_S,
        )

        # Hold the pose briefly at the top of the yawn.
        reachy_mini.goto_target(
            head=rise_pose,
            antennas=[self.ANTENNAS_LOWERED_RAD, -self.ANTENNAS_LOWERED_RAD],
            duration=self.HOLD_DURATION_S,
        )

        neutral_pose = create_head_pose(pitch=0.0, degrees=True)
        reachy_mini.goto_target(
            head=neutral_pose, antennas=[0.0, 0.0], duration=self.RELEASE_DURATION_S
        )
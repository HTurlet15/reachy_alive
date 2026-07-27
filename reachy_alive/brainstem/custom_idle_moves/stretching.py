import time

from reachy_mini import ReachyMini
from reachy_mini.utils import create_head_pose

from reachy_alive.move import Move


class Stretching(Move):
    """Plays a hand-made stretch: reach up, hold, tremble, release.

    No move in the official emotions library matches "stretch" (checked
    via list_moves() on 2026-07-26), so this is fully procedural.
    """

    REACH_UP_PITCH_DEG = -25.0   # negative to tilt head up
    REACH_UP_Z_MM = 15.0         # head extends upward
    ANTENNAS_DOWN_RAD = -1.0     # lowered, "winding up" position
    ANTENNAS_UP_RAD = 1.4        # extended straight, "reaching" position
    TREMBLE_AMPLITUDE_RAD = 0.15
    TREMBLE_DURATION_S = 0.6
    TREMBLE_STEP_S = 0.03        # short bursts on purpose

    def trigger(self, reachy_mini: ReachyMini) -> None:
        wind_up_pose = create_head_pose(pitch=0.0, z=0.0, degrees=True, mm=True)
        reachy_mini.goto_target(
            head=wind_up_pose,
            antennas=[self.ANTENNAS_DOWN_RAD, -self.ANTENNAS_DOWN_RAD],
            duration=0.5,
        )

        reach_pose = create_head_pose(
            pitch=self.REACH_UP_PITCH_DEG, z=self.REACH_UP_Z_MM, degrees=True, mm=True
        )
        reachy_mini.goto_target(
            head=reach_pose,
            antennas=[self.ANTENNAS_UP_RAD, -self.ANTENNAS_UP_RAD],
            duration=0.8,
        )

        start = time.time()
        while time.time() - start < self.TREMBLE_DURATION_S:
            step = int((time.time() - start) / self.TREMBLE_STEP_S)
            offset = self.TREMBLE_AMPLITUDE_RAD * (1 if step % 2 == 0 else -1)
            reachy_mini.set_target(
                head=reach_pose,
                antennas=[self.ANTENNAS_UP_RAD + offset, -self.ANTENNAS_UP_RAD - offset],
            )
            time.sleep(self.TREMBLE_STEP_S)

        neutral_pose = create_head_pose(pitch=0.0, z=0.0, degrees=True, mm=True)
        reachy_mini.goto_target(head=neutral_pose, antennas=[0.0, 0.0], duration=1.0)
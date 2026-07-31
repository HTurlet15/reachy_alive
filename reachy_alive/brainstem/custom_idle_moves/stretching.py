# reachy_alive/brainstem/custom_idle_moves/stretching.py
"""Hand-made stretch gesture: crouch, rise with a tremble, release."""

import time

import numpy as np
from reachy_mini import ReachyMini
from reachy_mini.utils import create_head_pose

from reachy_alive.move import Move


class Stretching(Move):
    """Plays a hand-made stretch: crouch, rise with a tremble, release."""

    CROUCH_FRACTION = 0.15
    RISE_FRACTION = 0.5
    STRETCH_DURATION_S = 2.8
    STEP_S = 0.03
    RELEASE_DURATION_S = 1.0

    LOWER_PITCH_DEG = 20.0
    ANTENNAS_DOWN_DEG = -55.0
    CROUCH_Z_MM = -8.0

    MAX_Z_MM = 15.0
    REACH_ROLL_DEG = 10.0
    ANTENNAS_UP_DEG = 5.0

    TREMBLE_Z_OSCILLATION_MM = 1.0
    TREMBLE_ANTENNA_AMPLITUDE_DEG = 8.6
    TREMBLE_LOOK_UP_PITCH_DEG = -15.0

    def trigger(self, reachy_mini: ReachyMini) -> None:
        # TODO: play a stretch/effort sound once a .wav asset is chosen.

        # Convert the previous values from degrees to radians
        antennas_down_rad = np.deg2rad(self.ANTENNAS_DOWN_DEG)
        antennas_up_rad = np.deg2rad(self.ANTENNAS_UP_DEG)
        tremble_antenna_rad = np.deg2rad(self.TREMBLE_ANTENNA_AMPLITUDE_DEG)

        #Calculating the proportion of time spent on each phase of the movement
        crouch_end = self.CROUCH_FRACTION
        rise_end = self.CROUCH_FRACTION + self.RISE_FRACTION
        tremble_span = 1.0 - rise_end

        start = time.time()
        step = 0

        while time.time() - start < self.STRETCH_DURATION_S:
            progress = (time.time() - start) / self.STRETCH_DURATION_S

            if progress < crouch_end:
                pitch, z, roll, antenna_target = self._crouch_pose(progress/crouch_end, antennas_down_rad)
            elif progress < rise_end:
                pitch, z, roll, antenna_target = self._rise_pose((progress - crouch_end) / self.RISE_FRACTION, antennas_down_rad, antennas_up_rad)
            else:
                pitch, z, roll, antenna_target = self._tremble_pose((progress - rise_end) / tremble_span, step, antennas_up_rad, tremble_antenna_rad)

            pose = create_head_pose(pitch=pitch, z=z, roll=roll, degrees=True, mm=True)
            reachy_mini.set_target(head=pose, antennas=[antenna_target, -antenna_target])

            step += 1
            time.sleep(self.STEP_S)

        neutral_pose = create_head_pose(pitch=0.0, z=0.0, roll=0.0, degrees=True, mm=True)
        reachy_mini.goto_target(
            head=neutral_pose, antennas=[0.0, 0.0], duration=self.RELEASE_DURATION_S
        )

    def _crouch_pose(self, p: float, antennas_down_rad: float) -> tuple[float, float, float, float]:
        """Interpolate crouch phase. p: 0 (neutral) -> 1 (fully crouched)."""

        pitch = p * self.LOWER_PITCH_DEG
        z = p * self.CROUCH_Z_MM
        roll = 0.0
        antenna_target = p * antennas_down_rad

        return pitch, z, roll, antenna_target

    def _rise_pose(self, p: float, antennas_down_rad: float, antennas_up_rad: float) -> tuple[float, float, float, float]:
        """Interpolate rise phase. p: 0 (crouched) -> 1 (fully extended)."""

        pitch = self.LOWER_PITCH_DEG * (1 - p)
        z = self.CROUCH_Z_MM + p * (self.MAX_Z_MM - self.CROUCH_Z_MM)
        roll = p * self.REACH_ROLL_DEG
        antenna_target = antennas_down_rad + p * (antennas_up_rad - antennas_down_rad)

        return pitch, z, roll, antenna_target

    def _tremble_pose(self, p: float, step: int, antennas_up_rad: float, tremble_antenna_rad: float) -> tuple[float, float, float, float]:
        """Interpolate tremble phase. p: 0 -> 1 across the phase."""

        sign = 1 if step % 2 == 0 else -1
        pitch = p * self.TREMBLE_LOOK_UP_PITCH_DEG
        z = self.MAX_Z_MM + sign * self.TREMBLE_Z_OSCILLATION_MM
        roll = self.REACH_ROLL_DEG
        antenna_target = antennas_up_rad + sign * tremble_antenna_rad

        return pitch, z, roll, antenna_target
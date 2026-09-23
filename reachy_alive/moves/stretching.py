"""Hand-made stretch gesture: crouch, rise, tremble at full extension, release.

See moves/README.md for how to write a move.
"""

import numpy as np
from reachy_mini.utils import create_head_pose

from reachy_alive.interpolate import interpolate
from reachy_alive.moves.base import (
    NEUTRAL_ANTENNAS_RAD,
    NEUTRAL_BODY_YAW_RAD,
    Move,
    PhasedMove,
)


class Stretching(PhasedMove):
    """Plays a stretch: the robot gathers down, extends, trembles, releases."""

    SOUNDS_DIR = Move.SOUNDS_DIR / "stretching"

    PHASE_SOUNDS = {
        "crouch": None,
        "rise": "rising.wav",
        "tremble": "stretching.wav",
        "release": "exhale.wav",
    }
    SILENT_PHASE_DURATIONS_S = {"crouch": 0.4}

    LOWER_PITCH_DEG = 20.0
    CROUCH_Z_MM = -8.0
    MAX_Z_MM = 15.0
    REACH_ROLL_DEG = 10.0

    TREMBLE_Z_OSCILLATION_MM = 1.0
    TREMBLE_LOOK_UP_PITCH_DEG = -15.0

    # Both antennas move together, mirrored: one value drives the pair.
    ANTENNA_AT_NEUTRAL_RAD = NEUTRAL_ANTENNAS_RAD[0]
    ANTENNA_DOWN_RAD = np.deg2rad(-55.0)
    ANTENNA_UP_RAD = np.deg2rad(5.0)
    TREMBLE_ANTENNA_AMPLITUDE_RAD = np.deg2rad(8.6)

    def _pose_at(
        self, phase: str, p: float, step: int
    ) -> tuple[np.ndarray, list[float], float]:
        if phase == "crouch":
            return self._crouch_pose(p)
        if phase == "rise":
            return self._rise_pose(p)
        if phase == "tremble":
            return self._tremble_pose(p, step)
        return self._release_pose(p)

    def _crouch_pose(self, p: float) -> tuple[np.ndarray, list[float], float]:
        """Gather down before the stretch. p: 0 -> 1."""
        head = create_head_pose(
            pitch=interpolate(0.0, self.LOWER_PITCH_DEG, p),
            z=interpolate(0.0, self.CROUCH_Z_MM, p),
            degrees=True,
            mm=True,
        )
        antenna = interpolate(self.ANTENNA_AT_NEUTRAL_RAD, self.ANTENNA_DOWN_RAD, p)
        return head, [antenna, -antenna], NEUTRAL_BODY_YAW_RAD

    def _rise_pose(self, p: float) -> tuple[np.ndarray, list[float], float]:
        """Extend upward and roll slightly to the side. p: 0 -> 1."""
        head = create_head_pose(
            pitch=interpolate(self.LOWER_PITCH_DEG, 0.0, p),
            z=interpolate(self.CROUCH_Z_MM, self.MAX_Z_MM, p),
            roll=interpolate(0.0, self.REACH_ROLL_DEG, p),
            degrees=True,
            mm=True,
        )
        antenna = interpolate(self.ANTENNA_DOWN_RAD, self.ANTENNA_UP_RAD, p)
        return head, [antenna, -antenna], NEUTRAL_BODY_YAW_RAD

    def _tremble_pose(self, p: float, step: int) -> tuple[np.ndarray, list[float], float]:
        """Hold at full extension, shaking with effort. p: 0 -> 1."""
        sign = 1 if step % 2 == 0 else -1
        head = create_head_pose(
            pitch=interpolate(0.0, self.TREMBLE_LOOK_UP_PITCH_DEG, p),
            z=self.MAX_Z_MM + sign * self.TREMBLE_Z_OSCILLATION_MM,
            roll=self.REACH_ROLL_DEG,
            degrees=True,
            mm=True,
        )
        antenna = self.ANTENNA_UP_RAD + sign * self.TREMBLE_ANTENNA_AMPLITUDE_RAD
        return head, [antenna, -antenna], NEUTRAL_BODY_YAW_RAD

    def _release_pose(self, p: float) -> tuple[np.ndarray, list[float], float]:
        """Ease back to neutral. p: 0 -> 1."""
        head = create_head_pose(
            pitch=interpolate(self.TREMBLE_LOOK_UP_PITCH_DEG, 0.0, p),
            z=interpolate(self.MAX_Z_MM, 0.0, p),
            roll=interpolate(self.REACH_ROLL_DEG, 0.0, p),
            degrees=True,
            mm=True,
        )
        antenna = interpolate(self.ANTENNA_UP_RAD, self.ANTENNA_AT_NEUTRAL_RAD, p)
        return head, [antenna, -antenna], NEUTRAL_BODY_YAW_RAD
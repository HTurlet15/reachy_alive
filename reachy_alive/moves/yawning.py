"""Hand-made yawn gesture: rise, hold, exhale back to neutral, shake off sleep.

This is the reference procedural move. See moves/README.md for how to
write one.
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


class Yawning(PhasedMove):
    """Plays a yawn: the head rises, holds, eases back down, then shakes."""

    SOUNDS_DIR = Move.SOUNDS_DIR / "yawning"

    PHASE_SOUNDS = {
        "rise": "inhale.wav",
        "hold": None,
        "exhale": "exhale.wav",
        "shake": "shake.wav",
    }
    SILENT_PHASE_DURATIONS_S = {"hold": 0.7}
    PHASE_PADDING_S = {
        "rise": 0.5,
        "exhale": 0.6,
    }

    RISE_PITCH_DEG = -20.0

    # Both antennas move together, mirrored: one value drives the pair.
    ANTENNA_AT_NEUTRAL_RAD = NEUTRAL_ANTENNAS_RAD[0]
    ANTENNA_LOWERED_RAD = -1.0

    SHAKE_YAW_AMPLITUDE_DEG = 12.5
    SHAKE_ALTERNATION_STEPS = 5  # ticks held per side

    def _pose_at(
        self, phase: str, p: float, step: int, elapsed_s: float
    ) -> tuple[np.ndarray, list[float], float]:
        if phase == "rise":
            return self._rise_pose(p)
        if phase == "hold":
            return self._hold_pose()
        if phase == "exhale":
            return self._exhale_pose(p)
        return self._shake_pose(step)

    def _rise_pose(self, p: float) -> tuple[np.ndarray, list[float], float]:
        """Tilt the head up and lower the antennas. p: 0 -> 1."""
        pitch = interpolate(0.0, self.RISE_PITCH_DEG, p)
        antenna = interpolate(self.ANTENNA_AT_NEUTRAL_RAD, self.ANTENNA_LOWERED_RAD, p)
        head = create_head_pose(pitch=pitch, degrees=True)
        return head, [antenna, -antenna], NEUTRAL_BODY_YAW_RAD

    def _hold_pose(self) -> tuple[np.ndarray, list[float], float]:
        """Stay at the fully risen pose."""
        head = create_head_pose(pitch=self.RISE_PITCH_DEG, degrees=True)
        antennas = [self.ANTENNA_LOWERED_RAD, -self.ANTENNA_LOWERED_RAD]
        return head, antennas, NEUTRAL_BODY_YAW_RAD

    def _exhale_pose(self, p: float) -> tuple[np.ndarray, list[float], float]:
        """Ease the head and antennas back to neutral. p: 0 -> 1."""
        pitch = interpolate(self.RISE_PITCH_DEG, 0.0, p)
        antenna = interpolate(self.ANTENNA_LOWERED_RAD, self.ANTENNA_AT_NEUTRAL_RAD, p)
        head = create_head_pose(pitch=pitch, degrees=True)
        return head, [antenna, -antenna], NEUTRAL_BODY_YAW_RAD

    def _shake_pose(self, step: int) -> tuple[np.ndarray, list[float], float]:
        """Keep the head level while yaw alternates side to side.

        Only the head shakes -- the body stays facing forward.
        """
        sign = 1 if (step // self.SHAKE_ALTERNATION_STEPS) % 2 == 0 else -1
        yaw = sign * self.SHAKE_YAW_AMPLITUDE_DEG
        head = create_head_pose(yaw=yaw, degrees=True)
        return head, NEUTRAL_ANTENNAS_RAD, NEUTRAL_BODY_YAW_RAD
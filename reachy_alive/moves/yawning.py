import time
from pathlib import Path

from reachy_mini import ReachyMini
from reachy_mini.utils import create_head_pose

from reachy_alive.moves.base import Move


class Yawning(Move):
    """Plays a hand-made yawn: rise and hold, ease back to neutral, then shake off sleep."""

    RISE_FRACTION = 0.35
    HOLD_FRACTION = 0.3
    RETURN_FRACTION = 0.25

    # Phase boundaries as fractions of the whole gesture.
    RISE_END = RISE_FRACTION
    HOLD_END = RISE_END + HOLD_FRACTION
    RETURN_END = HOLD_END + RETURN_FRACTION
    SHAKE_SPAN = 1.0 - RETURN_END

    GESTURE_DURATION_S = 4
    RELEASE_DURATION_S = 1.0

    RISE_PITCH_DEG = -20.0
    ANTENNAS_LOWERED_RAD = -1.0

    SHAKE_YAW_AMPLITUDE_DEG = 12.5
    SHAKE_ALTERNATION_STEPS = 5  # ticks held per side before flipping

    ASSETS_DIR = Path(__file__).resolve().parents[1] / "assets" / "sounds"
    INHALE_SOUND_PATH = ASSETS_DIR / "inhale.wav"
    YAWN_SOUND_PATH = ASSETS_DIR / "yawning.wav"

    def __init__(self, tick_hz: float = 50.0) -> None:
        """
        Args:
            tick_hz: Frequency, in Hz, at which the pose is updated during the move.
        """
        self.step_s = 1.0 / tick_hz
        self._yawn_played = False

    def trigger(self, reachy_mini: ReachyMini) -> None:
        self._yawn_played = False
        reachy_mini.media.play_sound(str(self.INHALE_SOUND_PATH))

        start = time.monotonic()
        step = 0

        while time.monotonic() - start < self.GESTURE_DURATION_S:
            progress = (time.monotonic() - start) / self.GESTURE_DURATION_S
            pitch, yaw, antenna_target = self._pose_at(progress, step)

            pose = create_head_pose(pitch=pitch, yaw=yaw, degrees=True)
            reachy_mini.set_target(head=pose, antennas=[antenna_target, -antenna_target])

            if progress >= self.RISE_END and not self._yawn_played:
                reachy_mini.media.play_sound(str(self.YAWN_SOUND_PATH))
                self._yawn_played = True

            step += 1
            time.sleep(self.step_s)

        neutral_pose = create_head_pose(pitch=0.0, yaw=0.0, degrees=True)
        reachy_mini.goto_target(
            head=neutral_pose, antennas=[0.0, 0.0], duration=self.RELEASE_DURATION_S
        )

    def _pose_at(self, progress: float, step: int) -> tuple[float, float, float]:
        """Dispatch to the phase matching progress. progress: 0 -> 1 across the whole gesture."""

        if progress < self.RISE_END:
            return self._rise_pose(progress / self.RISE_FRACTION)
        elif progress < self.HOLD_END:
            return self._hold_pose()
        elif progress < self.RETURN_END:
            return self._return_pose((progress - self.HOLD_END) / self.RETURN_FRACTION)
        else:
            return self._shake_pose(step)

    def _rise_pose(self, p: float) -> tuple[float, float, float]:
        """Interpolate rise phase. p: 0 (neutral) -> 1 (fully risen)."""

        pitch = p * self.RISE_PITCH_DEG
        antenna_target = p * self.ANTENNAS_LOWERED_RAD
        return pitch, 0.0, antenna_target

    def _hold_pose(self) -> tuple[float, float, float]:
        """Hold at the fully risen pose."""

        return self.RISE_PITCH_DEG, 0.0, self.ANTENNAS_LOWERED_RAD

    def _return_pose(self, p: float) -> tuple[float, float, float]:
        """Interpolate return phase. p: 0 (risen) -> 1 (neutral)."""

        pitch = self.RISE_PITCH_DEG * (1 - p)
        antenna_target = self.ANTENNAS_LOWERED_RAD * (1 - p)
        return pitch, 0.0, antenna_target

    def _shake_pose(self, step: int) -> tuple[float, float, float]:
        """Shake phase: head stays neutral, yaw alternates side to side by tick."""

        sign = 1 if (step // self.SHAKE_ALTERNATION_STEPS) % 2 == 0 else -1
        yaw = sign * self.SHAKE_YAW_AMPLITUDE_DEG
        return 0.0, yaw, 0.0

import time
from pathlib import Path

from reachy_mini import ReachyMini
from reachy_mini.utils import create_head_pose

from reachy_alive.moves.base import Move

ASSETS_DIR = Path(__file__).resolve().parents[1] / "assets" / "sounds"


class Yawning(Move):
    """Plays a hand-made yawn: rise and hold in one continuous motion, release."""

    RISE_FRACTION = 0.5  # fraction of RISE_HOLD_DURATION_S spent rising; remainder holds
    RISE_HOLD_DURATION_S = 2.3
    STEP_S = 0.03
    RELEASE_DURATION_S = 1.0

    RISE_PITCH_DEG = -20.0
    ANTENNAS_LOWERED_RAD = -1.0

    INHALE_SOUND_PATH = ASSETS_DIR / "inhale.wav"
    YAWN_SOUND_PATH = ASSETS_DIR / "yawning.wav"

    def __init__(self) -> None:
        self._yawn_played = False

    def trigger(self, reachy_mini: ReachyMini) -> None:
        reachy_mini.media.play_sound(str(self.INHALE_SOUND_PATH))

        start = time.time()
        while time.time() - start < self.RISE_HOLD_DURATION_S:
            progress = (time.time() - start) / self.RISE_HOLD_DURATION_S
            pitch, antenna_target = self._rise_and_hold_pose(progress)

            pose = create_head_pose(pitch=pitch, degrees=True)
            reachy_mini.set_target(head=pose, antennas=[antenna_target, -antenna_target])
            time.sleep(self.STEP_S)

            if progress >= self.RISE_FRACTION and not self._yawn_played:
                reachy_mini.media.play_sound(str(self.YAWN_SOUND_PATH))
                self._yawn_played = True

        neutral_pose = create_head_pose(pitch=0.0, degrees=True)
        reachy_mini.goto_target(
            head=neutral_pose, antennas=[0.0, 0.0], duration=self.RELEASE_DURATION_S
        )

    def _rise_and_hold_pose(self, progress: float) -> tuple[float, float]:
        """Interpolate rise-then-hold. progress: 0 -> 1 across the whole phase."""
        rise_progress = min(progress / self.RISE_FRACTION, 1.0)
        pitch = rise_progress * self.RISE_PITCH_DEG
        antenna_target = rise_progress * self.ANTENNAS_LOWERED_RAD
        return pitch, antenna_target
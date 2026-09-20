import itertools
import time

import soundfile as sf
from reachy_mini import ReachyMini
from reachy_mini.utils import create_head_pose

from reachy_alive.moves.base import Move


class Yawning(Move):
    """Plays a hand-made yawn: rise, hold, exhale back to neutral, then shake off sleep.

    Phase durations come from the sound files, so the motion stays in sync
    with the audio even if a sound is re-exported at a different length.
    """

    SOUNDS_DIR = Move.SOUNDS_DIR / "yawning"

    # Ordered phases, with the sound played at the start of each.
    # A phase with no sound uses HOLD_DURATION_S.
    PHASE_SOUNDS = {
        "rise": "inhale.wav",
        "hold": None,
        "exhale": "exhale.wav",
        "shake": "shake.wav",
    }
    HOLD_DURATION_S = 0.7

    PHASE_PADDING_S = {"exhale": 0.6}
    
    RISE_PITCH_DEG = -20.0
    ANTENNAS_LOWERED_RAD = -1.0

    SHAKE_YAW_AMPLITUDE_DEG = 12.5
    SHAKE_ALTERNATION_STEPS = 5  # ticks held per side before flipping

    def __init__(self, tick_hz: float = 50.0) -> None:
        """
        Args:
            tick_hz: Frequency, in Hz, at which the pose is updated during the move.
        """
        self.step_s = 1.0 / tick_hz

        durations = [self._phase_duration(phase) for phase in self.PHASE_SOUNDS]
        self.phase_ends_s = dict(zip(self.PHASE_SOUNDS, itertools.accumulate(durations)))
        self.duration_s = sum(durations)

    def _phase_duration(self, phase: str) -> float:
        """How long a phase lasts: its sound's length, plus any padding.

        Args:
            phase: Name of the phase.

        Returns:
            Duration in seconds.
        """
        sound = self.PHASE_SOUNDS[phase]
        sound_duration = (
            self.HOLD_DURATION_S
            if sound is None
            else sf.info(str(self.SOUNDS_DIR / sound)).duration
        )
        return sound_duration + self.PHASE_PADDING_S.get(phase, 0.0)

    def _perform(self, reachy_mini: ReachyMini) -> None:
        start = time.monotonic()
        step = 0
        previous_phase = None

        while (elapsed := time.monotonic() - start) < self.duration_s:
            phase, phase_progress = self._phase_at(elapsed)

            if phase != previous_phase:
                self._play_phase_sound(reachy_mini, phase)
                previous_phase = phase

            pitch, yaw, antenna_target = self._pose_at(phase, phase_progress, step)
            pose = create_head_pose(pitch=pitch, yaw=yaw, degrees=True)
            reachy_mini.set_target(head=pose, antennas=[antenna_target, -antenna_target])

            step += 1
            time.sleep(self.step_s)

    def _phase_at(self, elapsed: float) -> tuple[str, float]:
        """Find the running phase and how far into it we are.

        Args:
            elapsed: Seconds since the gesture started.

        Returns:
            (phase name, local progress from 0 to 1).
        """
        phase_start = 0.0
        for phase, phase_end in self.phase_ends_s.items():
            if elapsed < phase_end:
                return phase, (elapsed - phase_start) / (phase_end - phase_start)
            phase_start = phase_end
        return phase, 1.0

    def _play_phase_sound(self, reachy_mini: ReachyMini, phase: str) -> None:
        """Play the sound a phase starts with, if it has one."""
        sound = self.PHASE_SOUNDS[phase]
        if sound is not None:
            reachy_mini.media.play_sound(str(self.SOUNDS_DIR / sound))

    def _pose_at(
        self, phase: str, phase_progress: float, step: int
    ) -> tuple[float, float, float]:
        """Dispatch to the pose of the running phase.

        Args:
            phase: Name of the running phase.
            phase_progress: Local progress within that phase, 0 to 1.
            step: Tick counter, used by the shake.

        Returns:
            (pitch, yaw, antenna target).
        """
        if phase == "rise":
            return self._rise_pose(phase_progress)
        if phase == "hold":
            return self._hold_pose()
        if phase == "exhale":
            return self._exhale_pose(phase_progress)
        return self._shake_pose(step)

    def _rise_pose(self, p: float) -> tuple[float, float, float]:
        """Head tilts up, antennas lower. p: 0 (neutral) -> 1 (fully risen)."""
        return p * self.RISE_PITCH_DEG, 0.0, p * self.ANTENNAS_LOWERED_RAD

    def _hold_pose(self) -> tuple[float, float, float]:
        """Hold at the fully risen pose."""
        return self.RISE_PITCH_DEG, 0.0, self.ANTENNAS_LOWERED_RAD

    def _exhale_pose(self, p: float) -> tuple[float, float, float]:
        """Ease back down. p: 0 (risen) -> 1 (neutral)."""
        return (
            self.RISE_PITCH_DEG * (1 - p),
            0.0,
            self.ANTENNAS_LOWERED_RAD * (1 - p),
        )

    def _shake_pose(self, step: int) -> tuple[float, float, float]:
        """Head stays level, yaw alternates side to side."""
        sign = 1 if (step // self.SHAKE_ALTERNATION_STEPS) % 2 == 0 else -1
        return 0.0, sign * self.SHAKE_YAW_AMPLITUDE_DEG, 0.0
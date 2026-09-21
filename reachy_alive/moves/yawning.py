"""Hand-made yawn gesture: rise, hold, exhale back to neutral, shake off sleep.

This is the reference procedural move. See moves/README.md for how to
write one.
"""

import itertools
import time
from pathlib import Path

import soundfile as sf
from reachy_mini import ReachyMini
from reachy_mini.utils import create_head_pose

from reachy_alive.moves.base import NEUTRAL_ANTENNAS_RAD, Move
from reachy_alive.interpolate import interpolate

class Yawning(Move):
    """Plays a yawn whose phase durations follow its sound files.

    Re-exporting a sound at a different length stretches or shrinks the
    matching phase, so motion and audio stay in sync.
    """

    SOUNDS_DIR = Move.SOUNDS_DIR / "yawning"

    # Ordered phases and the sound each one starts with. A phase without a
    # sound lasts HOLD_DURATION_S.
    PHASE_SOUNDS = {
        "rise": "inhale.wav",
        "hold": None,
        "exhale": "exhale.wav",
        "shake": "shake.wav",
    }
    HOLD_DURATION_S = 0.7

    # Extra silence after a phase's sound, in seconds.
    PHASE_PADDING_S = {
        "rise": 0.5,
        "exhale": 0.6,
    }

    RISE_PITCH_DEG = -20.0

    # Antennas move as a mirrored pair, sent as [a, -a]; poses compute `a`.
    ANTENNA_AT_NEUTRAL_RAD = NEUTRAL_ANTENNAS_RAD[0]
    ANTENNA_LOWERED_RAD = -1.0

    SHAKE_YAW_AMPLITUDE_DEG = 12.5
    SHAKE_ALTERNATION_STEPS = 5  # ticks held per side

    def __init__(self, tick_hz: float = 50.0) -> None:
        """Read each phase's duration from its sound file.

        Args:
            tick_hz: Frequency, in Hz, at which the pose is updated.

        Raises:
            ValueError: If PHASE_PADDING_S names a phase that doesn't exist.
            FileNotFoundError: If a sound file is missing.
        """
        unknown = set(self.PHASE_PADDING_S) - set(self.PHASE_SOUNDS)
        if unknown:
            raise ValueError(f"PHASE_PADDING_S names unknown phases: {sorted(unknown)}")

        self.step_s = 1.0 / tick_hz

        durations = [self._phase_duration(phase) for phase in self.PHASE_SOUNDS]
        self.phase_ends_s = dict(zip(self.PHASE_SOUNDS, itertools.accumulate(durations)))
        self.duration_s = sum(durations)

    def sound_paths(self) -> list[Path]:
        """List the sounds this move plays, uploaded before it starts."""
        return [self.SOUNDS_DIR / s for s in self.PHASE_SOUNDS.values() if s is not None]

    def _perform(self, reachy_mini: ReachyMini) -> None:
        """Run the gesture, firing each phase's sound as the phase begins."""
        start = time.monotonic()
        step = 0
        previous_phase = None

        while (elapsed := time.monotonic() - start) < self.duration_s:
            phase, phase_progress = self._phase_at(elapsed)

            # Local, so nothing carries over between plays.
            if phase != previous_phase:
                self._play_phase_sound(reachy_mini, phase)
                previous_phase = phase

            pitch, yaw, antenna = self._pose_at(phase, phase_progress, step)
            pose = create_head_pose(pitch=pitch, yaw=yaw, degrees=True)
            reachy_mini.set_target(head=pose, antennas=[antenna, -antenna])

            step += 1
            time.sleep(self.step_s)

    def _phase_duration(self, phase: str) -> float:
        """Return a phase's duration: its sound's length plus any padding.

        Args:
            phase: Name of the phase.

        Returns:
            Duration in seconds.

        Raises:
            FileNotFoundError: If the phase's sound file is missing.
        """
        padding = self.PHASE_PADDING_S.get(phase, 0.0)
        sound = self.PHASE_SOUNDS[phase]
        if sound is None:
            return self.HOLD_DURATION_S + padding

        path = self.SOUNDS_DIR / sound
        if not path.is_file():
            raise FileNotFoundError(f"Sound for phase {phase!r} not found: {path}")

        return sf.info(str(path)).duration + padding

    def _phase_at(self, elapsed: float) -> tuple[str, float]:
        """Return the running phase and the progress within it.

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

        # elapsed can overshoot the last phase by a fraction of a tick.
        return list(self.phase_ends_s)[-1], 1.0

    def _play_phase_sound(self, reachy_mini: ReachyMini, phase: str) -> None:
        """Play the sound a phase starts with, if it has one."""
        sound = self.PHASE_SOUNDS[phase]
        if sound is not None:
            self.play_sound(reachy_mini, self.SOUNDS_DIR / sound)

    def _pose_at(
        self, phase: str, phase_progress: float, step: int
    ) -> tuple[float, float, float]:
        """Return the pose for the running phase.

        Args:
            phase: Name of the running phase.
            phase_progress: Progress within that phase, 0 to 1.
            step: Tick counter, used by the shake.

        Returns:
            (pitch in degrees, yaw in degrees, antenna angle in radians).
        """
        if phase == "rise":
            return self._rise_pose(phase_progress)
        if phase == "hold":
            return self._hold_pose()
        if phase == "exhale":
            return self._exhale_pose(phase_progress)
        return self._shake_pose(step)

    def _rise_pose(self, p: float) -> tuple[float, float, float]:
        """Tilt the head up and lower the antennas. p: 0 -> 1."""
        pitch = interpolate(0.0, self.RISE_PITCH_DEG, p)
        antenna = interpolate(self.ANTENNA_AT_NEUTRAL_RAD, self.ANTENNA_LOWERED_RAD, p)
        return pitch, 0.0, antenna

    def _hold_pose(self) -> tuple[float, float, float]:
        """Stay at the fully risen pose."""
        return self.RISE_PITCH_DEG, 0.0, self.ANTENNA_LOWERED_RAD

    def _exhale_pose(self, p: float) -> tuple[float, float, float]:
        """Ease the head and antennas back to neutral. p: 0 -> 1."""
        pitch = interpolate(self.RISE_PITCH_DEG, 0.0, p)
        antenna = interpolate(self.ANTENNA_LOWERED_RAD, self.ANTENNA_AT_NEUTRAL_RAD, p)
        return pitch, 0.0, antenna

    def _shake_pose(self, step: int) -> tuple[float, float, float]:
        """Keep the head level while yaw alternates side to side."""
        sign = 1 if (step // self.SHAKE_ALTERNATION_STEPS) % 2 == 0 else -1
        return 0.0, sign * self.SHAKE_YAW_AMPLITUDE_DEG, self.ANTENNA_AT_NEUTRAL_RAD
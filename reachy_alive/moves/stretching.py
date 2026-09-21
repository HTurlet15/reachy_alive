"""Hand-made stretch gesture: crouch, rise, hold with a tremble, then release."""

import itertools
import time

import numpy as np
import soundfile as sf
from reachy_mini import ReachyMini
from reachy_mini.utils import create_head_pose

from reachy_alive.moves.base import Move


class Stretching(Move):
    """Plays a hand-made stretch: crouch, rise, tremble at full extension, release.

    Phase durations come from the sound files, so the motion stays in sync
    with the audio even if a sound is re-exported at a different length.
    """

    SOUNDS_DIR = Move.SOUNDS_DIR / "stretching"

    # The gesture, in order. Each phase plays its sound as it starts, and
    # lasts as long as that sound. A phase with no sound needs an explicit
    # duration -- see CROUCH_DURATION_S.
    PHASE_SOUNDS = {
        "crouch": None,
        "rise": "rising.wav",
        "tremble": "stretching.wav",
        "release": "exhale.wav",
    }
    CROUCH_DURATION_S = 0.5

    # Extra silence added to a phase, on top of its sound. Use this to let
    # a phase breathe before the next one starts, rather than editing the
    # .wav itself.
    PHASE_PADDING_S = {"rise": 0,
                       "tremble" : 0.25}

    LOWER_PITCH_DEG = 20.0
    ANTENNAS_DOWN_DEG = -55.0
    CROUCH_Z_MM = -8.0

    MAX_Z_MM = 15.0
    REACH_ROLL_DEG = 10.0
    ANTENNAS_UP_DEG = 5.0

    TREMBLE_Z_OSCILLATION_MM = 1.0
    TREMBLE_ANTENNA_AMPLITUDE_DEG = 8.6
    TREMBLE_LOOK_UP_PITCH_DEG = -15.0

    def __init__(self, tick_hz: float = 50.0) -> None:
        """
        Args:
            tick_hz: Frequency, in Hz, at which the pose is updated during the move.

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

        self.antennas_down_rad = np.deg2rad(self.ANTENNAS_DOWN_DEG)
        self.antennas_up_rad = np.deg2rad(self.ANTENNAS_UP_DEG)
        self.tremble_antenna_rad = np.deg2rad(self.TREMBLE_ANTENNA_AMPLITUDE_DEG)

    def _phase_duration(self, phase: str) -> float:
        """How long a phase lasts: its sound's length, plus any padding.

        Args:
            phase: Name of the phase.

        Returns:
            Duration in seconds.

        Raises:
            FileNotFoundError: If the phase's sound file is missing.
        """
        sound = self.PHASE_SOUNDS[phase]
        if sound is None:
            return self.CROUCH_DURATION_S + self.PHASE_PADDING_S.get(phase, 0.0)

        path = self.SOUNDS_DIR / sound
        if not path.is_file():
            raise FileNotFoundError(f"Sound for phase {phase!r} not found: {path}")

        return sf.info(str(path)).duration + self.PHASE_PADDING_S.get(phase, 0.0)

    def _perform(self, reachy_mini: ReachyMini) -> None:
        start = time.monotonic()
        step = 0
        previous_phase = None

        while (elapsed := time.monotonic() - start) < self.duration_s:
            phase, phase_progress = self._phase_at(elapsed)

            # Sounds fire on entering a phase. previous_phase is local, so
            # nothing carries over between calls -- no flag to reset.
            if phase != previous_phase:
                self._play_phase_sound(reachy_mini, phase)
                previous_phase = phase

            pitch, z, roll, antenna_target = self._pose_at(phase, phase_progress, step)
            pose = create_head_pose(pitch=pitch, z=z, roll=roll, degrees=True, mm=True)
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

        # Fallback: elapsed can overshoot the last phase end by a fraction of
        # a tick, since the while test and this call happen at slightly
        # different instants.
        return next(reversed(self.phase_ends_s)), 1.0

    def _play_phase_sound(self, reachy_mini: ReachyMini, phase: str) -> None:
        """Play the sound a phase starts with, if it has one."""
        sound = self.PHASE_SOUNDS[phase]
        if sound is not None:
            reachy_mini.media.play_sound(str(self.SOUNDS_DIR / sound))

    def _pose_at(
        self, phase: str, phase_progress: float, step: int
    ) -> tuple[float, float, float, float]:
        """Dispatch to the pose of the running phase.

        Args:
            phase: Name of the running phase.
            phase_progress: Local progress within that phase, 0 to 1.
            step: Tick counter, used by the tremble.

        Returns:
            (pitch, z, roll, antenna target).
        """
        if phase == "crouch":
            return self._crouch_pose(phase_progress)
        if phase == "rise":
            return self._rise_pose(phase_progress)
        if phase == "tremble":
            return self._tremble_pose(phase_progress, step)
        return self._release_pose(phase_progress)

    def _crouch_pose(self, p: float) -> tuple[float, float, float, float]:
        """Gather down. p: 0 (neutral) -> 1 (fully crouched)."""
        return (
            p * self.LOWER_PITCH_DEG,
            p * self.CROUCH_Z_MM,
            0.0,
            p * self.antennas_down_rad,
        )

    def _rise_pose(self, p: float) -> tuple[float, float, float, float]:
        """Extend upward. p: 0 (crouched) -> 1 (fully extended)."""
        return (
            self.LOWER_PITCH_DEG * (1 - p),
            self.CROUCH_Z_MM + p * (self.MAX_Z_MM - self.CROUCH_Z_MM),
            p * self.REACH_ROLL_DEG,
            self.antennas_down_rad
            + p * (self.antennas_up_rad - self.antennas_down_rad),
        )

    def _tremble_pose(self, p: float, step: int) -> tuple[float, float, float, float]:
        """Hold at full extension, shaking with effort. p: 0 -> 1 across the phase."""
        sign = 1 if step % 2 == 0 else -1
        return (
            p * self.TREMBLE_LOOK_UP_PITCH_DEG,
            self.MAX_Z_MM + sign * self.TREMBLE_Z_OSCILLATION_MM,
            self.REACH_ROLL_DEG,
            self.antennas_up_rad + sign * self.tremble_antenna_rad,
        )

    def _release_pose(self, p: float) -> tuple[float, float, float, float]:
        """Ease back to neutral. p: 0 (extended) -> 1 (neutral)."""
        return (
            self.TREMBLE_LOOK_UP_PITCH_DEG * (1 - p),
            self.MAX_Z_MM * (1 - p),
            self.REACH_ROLL_DEG * (1 - p),
            self.antennas_up_rad * (1 - p),
        )
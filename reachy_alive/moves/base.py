"""Base classes for the robot's moves.

There are two supported ways to write a move:

- ``PhasedMove``: a move written in code, or mixed with a recording.
- ``LibraryMove``: a move recorded in a Hugging Face dataset.

Every move is a ``Move``: it answers the SDK's move contract, ``duration``
and ``evaluate(t)``, plus the sounds it starts, ``sound_cues``. A move only
describes itself: the ActionSelector cuts it into one pose per tick, and
only the RobotController talks to the robot.

Two helpers shape motion: ``interpolate`` eases a value from one pose to
another, ``alternating_sign`` times shakes and trembles. Keep alternations
at 0.02 s per side or slower.

See ``moves/README.md`` for how to make a move.
"""

import itertools
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import soundfile as sf
from reachy_mini.motion.goto import GotoMove
from reachy_mini.motion.recorded_move import RecordedMoves
from reachy_mini.utils import create_head_pose
from reachy_mini.utils.interpolation import InterpolationTechnique

# The SDK's own neutral is offset ~10° off vertical, not [0.0, 0.0] --
# straight up is where antennas jitter (upstream hardware limit).
NEUTRAL_ANTENNAS_RAD = [-0.1745, 0.1745]

# Body facing forward. Moves that don't turn the body return this.
NEUTRAL_BODY_YAW_RAD = 0.0

# A recording's evaluate() raises at its last frame: read it just before,
# like the SDK's play_move.
RECORDING_END_MARGIN_S = 0.01


@dataclass(frozen=True)
class SoundCue:
    """A sound a move starts, and when.

    Attributes:
        at_s: Seconds since the move started.
        path: Local path of the sound, as the move's ``sound_cues`` name it.
    """

    at_s: float
    path: Path


def alternating_sign(elapsed_s: float, half_period_s: float) -> int:
    """Return +1 or -1, switching every half_period_s seconds.

    For motion that alternates rather than interpolates -- a shake or a
    tremble. Based on time, not on ticks, so the rhythm doesn't depend on
    how often the pose is updated. Keep half_period_s at 0.02 s or more:
    faster alternations don't reach the robot.

    Args:
        elapsed_s: Seconds since the move started.
        half_period_s: Seconds spent on each side.

    Returns:
        +1 during even half periods, -1 during odd ones.
    """
    return 1 if int(elapsed_s / half_period_s) % 2 == 0 else -1


def interpolate(start: float, end: float, p: float) -> float:
    """Return the value p of the way from start to end.

    For motion that eases from one pose to another within a phase: p = 0
    gives start, p = 1 gives end.

    Args:
        start: Value at the start of the motion.
        end: Value at the end of the motion.
        p: Progress, 0 to 1.

    Returns:
        The value between start and end.
    """
    return start + (end - start) * p


class Move(ABC):
    """A discrete, one-off move the robot can play.

    A move says what it does: it lasts ``duration`` seconds, ``evaluate(t)``
    gives its pose at any time, and ``sound_cues`` the sounds it starts.
    Before each play, ``draw_variations`` draws what changes from one play
    to the next.

    To write a move, subclass ``PhasedMove`` or use ``LibraryMove``.
    """

    SOUNDS_DIR = Path(__file__).resolve().parent.parent / "assets" / "sounds"

    # Set by every move when it's built.
    duration: float
    sound_cues: tuple[SoundCue, ...] = ()

    @property
    def name(self) -> str:
        """Identifier of the move, used in logs and by the app's page.

        Lowercase words joined by hyphens, like recorded moves. Derived from
        the class name by default: DeepBreath becomes deep-breath.
        """
        name = ""
        for char in type(self).__name__:
            if char.isupper() and name:
                name += "-"
            name += char.lower()
        return name

    def draw_variations(self) -> None:
        """Draw what varies between plays, once, before the first pose.

        Override it to draw a random angle, say; store it on self and read
        it when computing the pose. Does nothing by default.
        """

    @abstractmethod
    def evaluate(self, t: float) -> tuple[np.ndarray, list[float], float]:
        """Return the pose t seconds into the move. Never talk to the robot here.

        Args:
            t: Seconds since the move started, 0 to ``duration``.

        Returns:
            (head pose, antennas in ANTENNA_SIDES order (right, left), body
            yaw), angles in radians.
        """


class PhasedMove(Move):
    """A move built as a sequence of phases, each timed by its own sound.

    Declare the phases in ``PHASE_SOUNDS`` and write ``_pose_at``; override
    ``draw_variations`` to vary something between plays. Answers the SDK's move
    contract, ``duration`` and ``evaluate(t)``, plus ``sound_cues``.
    """

    # Ordered phases and the sound each one starts with, e.g.
    # {"rise": "inhale.wav", "hold": None}. Required.
    PHASE_SOUNDS: dict[str, str | None] = {}

    # Duration, in seconds, of the phases declared with no sound. Required
    # for each of them.
    SILENT_PHASE_DURATIONS_S: dict[str, float] = {}

    # Optional extra silence after a phase's sound, in seconds. Tune the
    # rhythm here rather than by editing the .wav files.
    PHASE_PADDING_S: dict[str, float] = {}

    def __init__(self) -> None:
        """Read each phase's duration from its sound file, and cue its sound.

        Raises:
            ValueError: If no phase is declared, if a phase with no sound
                has no duration, or if PHASE_PADDING_S names a phase that
                doesn't exist.
            FileNotFoundError: If a sound file is missing.
        """
        name = type(self).__name__
        if not self.PHASE_SOUNDS:
            raise ValueError(f"{name} declares no phases in PHASE_SOUNDS")

        untimed = {phase for phase, s in self.PHASE_SOUNDS.items() if s is None} - set(
            self.SILENT_PHASE_DURATIONS_S
        )
        if untimed:
            raise ValueError(
                f"{name}: phases with no sound need a duration in "
                f"SILENT_PHASE_DURATIONS_S: {sorted(untimed)}"
            )

        unknown = set(self.PHASE_PADDING_S) - set(self.PHASE_SOUNDS)
        if unknown:
            raise ValueError(f"{name}: PHASE_PADDING_S names unknown phases: {sorted(unknown)}")

        durations = [self._phase_duration(phase) for phase in self.PHASE_SOUNDS]
        phase_ends_s = itertools.accumulate(durations)
        self.phase_ends_s = dict(zip(self.PHASE_SOUNDS, phase_ends_s, strict=True))
        self.duration = sum(durations)

        # Each phase starts where the one before it ends.
        phase_starts_s = [0.0, *list(self.phase_ends_s.values())[:-1]]
        self.sound_cues = tuple(
            SoundCue(at_s=start_s, path=self.SOUNDS_DIR / sound)
            for start_s, sound in zip(phase_starts_s, self.PHASE_SOUNDS.values(), strict=True)
            if sound is not None
        )

    def evaluate(self, t: float) -> tuple[np.ndarray, list[float], float]:
        """Return the pose of the phase running t seconds into the move."""
        phase, phase_progress = self._phase_at(t)
        return self._pose_at(phase, phase_progress, t)

    @abstractmethod
    def _pose_at(
        self, phase: str, p: float, elapsed_s: float
    ) -> tuple[np.ndarray, list[float], float]:
        """Return the pose for the running phase.

        Only computes the pose: never talk to the robot here. Time anything
        rhythmic in seconds from ``elapsed_s``, never by counting calls.

        Args:
            phase: Name of the running phase.
            p: Progress within that phase, 0 to 1.
            elapsed_s: Seconds since the move started. Unlike ``p``, it
                doesn't reset between phases -- for moves that read a
                recording, which runs on a single timeline, and for motion
                that alternates, through ``alternating_sign``.

        Returns:
            (head pose, antennas in ANTENNA_SIDES order (right, left), body
            yaw), angles in radians. Return NEUTRAL_BODY_YAW_RAD if the move
            doesn't turn the body.
        """

    def _phase_duration(self, phase: str) -> float:
        """Return a phase's duration, in seconds: its sound's length plus any padding."""
        padding = self.PHASE_PADDING_S.get(phase, 0.0)
        sound = self.PHASE_SOUNDS[phase]
        if sound is None:
            return self.SILENT_PHASE_DURATIONS_S[phase] + padding

        path = self.SOUNDS_DIR / sound
        if not path.is_file():
            raise FileNotFoundError(f"Sound for phase {phase!r} not found: {path}")

        return sf.info(str(path)).duration + padding

    def _phase_at(self, elapsed_s: float) -> tuple[str, float]:
        """Return the running phase and the progress within it, from 0 to 1."""
        phase_start = 0.0
        for phase, phase_end in self.phase_ends_s.items():
            if elapsed_s < phase_end:
                return phase, (elapsed_s - phase_start) / (phase_end - phase_start)
            phase_start = phase_end

        # elapsed_s can overshoot the last phase by a fraction of a tick.
        return list(self.phase_ends_s)[-1], 1.0


class LibraryMove(Move):
    """Plays a named move from a recorded-moves library.

    Works with any Hugging Face dataset of recorded moves -- Pollen's own
    emotion library, or one you recorded in Marionette.
    """

    def __init__(self, move_name: str, library: RecordedMoves) -> None:
        """Load the recording, and cue its sound at the start, if it has one.

        Args:
            move_name: Name of the move in the library.
            library: The library to load it from.
        """
        self.move_name = move_name
        self._recording = library.get(move_name)
        self.duration = self._recording.duration

        sound = self._recording.sound_path
        if sound is not None:
            self.sound_cues = (SoundCue(at_s=0.0, path=sound),)

    @property
    def name(self) -> str:
        """The recording's name: every LibraryMove shares the same class."""
        return self.move_name

    def evaluate(self, t: float) -> tuple[np.ndarray, list[float], float]:
        """Return the recorded pose t seconds in."""
        return self._recording.evaluate(min(t, self.duration - RECORDING_END_MARGIN_S))


class ReturningToNeutral(Move):
    """Eases the robot back to the neutral pose, from wherever it is.

    The same path as the SDK's goto_target, which plays this GotoMove too;
    here it runs one pose at a time, like any move.
    """

    DURATION_S = 0.5

    def __init__(self, from_pose: tuple[np.ndarray, list[float], float]) -> None:
        """Plan the way back to neutral.

        Args:
            from_pose: (head pose, antennas, body yaw) to start from: the last
                pose sent to the robot.
        """
        head, antennas, body_yaw = from_pose
        self._goto = GotoMove(
            start_head_pose=head,
            target_head_pose=create_head_pose(),
            start_antennas=np.array(antennas),
            target_antennas=np.array(NEUTRAL_ANTENNAS_RAD),
            start_body_yaw=body_yaw,
            target_body_yaw=NEUTRAL_BODY_YAW_RAD,
            duration=self.DURATION_S,
            method=InterpolationTechnique.MIN_JERK,
        )
        self.duration = self._goto.duration

    def evaluate(self, t: float) -> tuple[np.ndarray, list[float], float]:
        """Return the pose t seconds into the way back."""
        return self._goto.evaluate(t)

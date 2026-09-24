"""Base class for every discrete gesture the robot can play.

Playing a move goes through three steps:

1. Its sounds are uploaded to the robot -- ahead of time if ``prepare``
   was called, otherwise right before the gesture.
2. The gesture itself runs -- this is ``_perform``, written by each move.
3. The robot returns to neutral, so the next behavior starts from a known
   pose.

To write a move, subclass ``Move`` and implement ``_perform`` and
``sound_paths``. Most gestures are a sequence of phases timed by their
sounds -- subclass ``PhasedMove`` instead and you only write the poses;
``yawning.py`` is the reference. A move recorded in a Hugging Face dataset
needs no code at all -- wrap it in ``LibraryMove``.
"""

import itertools
import time
from abc import ABC, abstractmethod
from pathlib import Path

import numpy as np
import soundfile as sf
from reachy_mini import ReachyMini
from reachy_mini.motion.recorded_move import RecordedMoves
from reachy_mini.utils import create_head_pose

# The SDK's own neutral is offset ~10° off vertical, not [0.0, 0.0] --
# straight up is where antennas jitter (upstream hardware limit).
NEUTRAL_ANTENNAS_RAD = [-0.1745, 0.1745]

# Body facing forward. Moves that don't turn the body return this.
NEUTRAL_BODY_YAW_RAD = 0.0


class Move(ABC):
    """A discrete, one-off gesture the robot can play.

    Subclasses implement ``_perform`` and ``sound_paths``. Callers only
    ever use ``play``, which handles everything around the gesture:
    uploading its sounds before it, and returning to neutral after it.
    """

    RETURN_DURATION_S = 0.5
    SOUNDS_DIR = Path(__file__).resolve().parent.parent / "assets" / "sounds"

    def play(self, reachy_mini: ReachyMini) -> None:
        """Play this move, then return the robot to neutral.

        Args:
            reachy_mini: Connected robot instance.
        """
        # None means nobody called prepare() yet -- the attribute doesn't
        # even exist before the first call -- so upload the sounds now.
        if getattr(self, "_remote_sounds", None) is None:
            self.prepare(reachy_mini)
        try:
            self._perform(reachy_mini)
            self.go_neutral(reachy_mini)
        finally:
            # Uploads are keyed by file name, and another move may overwrite
            # ours before this one plays again -- so the next play re-uploads.
            self._remote_sounds = None

    def prepare(self, reachy_mini: ReachyMini) -> None:
        """Upload this move's sounds ahead of time, so play() starts without a pause.

        Builds a table mapping each local sound file to what play_sound()
        should be given. There are two cases, depending on where the robot
        runs:

        - Wireless: the audio backend is a WebRTC client, which has an
          ``upload_sound`` method. Playing a local file would upload it over
          HTTP mid-gesture and freeze the motion, so each file is uploaded
          now, and the table points to its copy on the robot.
        - Local backend (simulation, Lite): files are read directly from
          disk, so there's nothing to upload. Each file points to itself.

        The table has the same shape either way, so play_sound() works the
        same on both.

        Optional: play() calls this itself if it wasn't done beforehand.
        Moves never call it.

        Args:
            reachy_mini: Connected robot instance.
        """
        audio = reachy_mini.media.audio
        paths = [str(path) for path in self.sound_paths()]
        if hasattr(audio, "upload_sound"):
            self._remote_sounds = {path: audio.upload_sound(path) for path in paths}
        else:
            self._remote_sounds = {path: path for path in paths}

    @abstractmethod
    def _perform(self, reachy_mini: ReachyMini) -> None:
        """Play the gesture itself. Free to end on any pose.

        Args:
            reachy_mini: Connected robot instance.
        """

    @abstractmethod
    def sound_paths(self) -> list[Path]:
        """List the local sound files this move plays.

        They get uploaded before the gesture starts. Return an empty list
        if the move plays no sound.

        Returns:
            Paths of the move's sound files.
        """

    def play_sound(self, reachy_mini: ReachyMini, path: Path) -> None:
        """Play one of this move's sounds, from the copy made by prepare().

        Args:
            reachy_mini: Connected robot instance.
            path: Local path of the sound, as listed in ``sound_paths``.

        Raises:
            KeyError: If the sound isn't listed in ``sound_paths``.
        """
        try:
            sound = self._remote_sounds[str(path)]
        except KeyError:
            raise KeyError(f"{path} is not listed in sound_paths()") from None
        reachy_mini.media.play_sound(sound)

    def go_neutral(self, reachy_mini: ReachyMini, duration: float | None = None) -> None:
        """Move the robot to the neutral head, antenna and body pose.

        Interpolated, so it's safe from any starting pose. Call it yourself
        mid-gesture if returning to neutral is part of the choreography.

        Args:
            reachy_mini: Connected robot instance.
            duration: Movement duration in seconds. Defaults to RETURN_DURATION_S.
        """
        reachy_mini.goto_target(
            head=create_head_pose(),
            antennas=NEUTRAL_ANTENNAS_RAD,
            body_yaw=NEUTRAL_BODY_YAW_RAD,
            duration=duration or self.RETURN_DURATION_S,
        )


class PhasedMove(Move):
    """A move built as a sequence of phases, each timed by its own sound.

    Declare the phases in ``PHASE_SOUNDS`` and write ``_pose_at``; this
    class handles the rest -- reading durations from the sound files,
    tracking which phase is running, firing its sound as it begins, and
    streaming poses to the robot.

    Re-exporting a sound at a different length stretches or shrinks the
    matching phase, so motion and audio stay in sync.
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

    def __init__(self, tick_hz: float = 50.0) -> None:
        """Read each phase's duration from its sound file.

        Args:
            tick_hz: Frequency, in Hz, at which the pose is updated.

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

        self.step_s = 1.0 / tick_hz

        durations = [self._phase_duration(phase) for phase in self.PHASE_SOUNDS]
        self.phase_ends_s = dict(zip(self.PHASE_SOUNDS, itertools.accumulate(durations)))
        self.duration_s = sum(durations)

    def sound_paths(self) -> list[Path]:
        """List the sounds this move plays, one per phase that has one."""
        return [self.SOUNDS_DIR / s for s in self.PHASE_SOUNDS.values() if s is not None]

    @abstractmethod
    def _pose_at(
        self, phase: str, p: float, step: int, elapsed_s: float
    ) -> tuple[np.ndarray, list[float], float]:
        """Return the pose for the running phase.

        Args:
            phase: Name of the running phase.
            p: Progress within that phase, 0 to 1.
            step: Tick counter, for motion that alternates rather than
                interpolates -- a shake or a tremble.
            elapsed_s: Seconds since the gesture started. Unlike ``p``, it
                doesn't reset between phases -- for moves that read a
                recording, which runs on a single timeline.

        Returns:
            (head pose, [left antenna, right antenna], body yaw), angles in
            radians. Return NEUTRAL_BODY_YAW_RAD if the move doesn't turn
            the body.
        """

    def _perform(self, reachy_mini: ReachyMini) -> None:
        """Run the gesture, firing each phase's sound as the phase begins."""
        start = time.monotonic()
        step = 0
        previous_phase = None

        while (elapsed_s := time.monotonic() - start) < self.duration_s:
            phase, phase_progress = self._phase_at(elapsed_s)

            # Local, so nothing carries over between plays.
            if phase != previous_phase:
                self._play_phase_sound(reachy_mini, phase)
                previous_phase = phase

            head, antennas, body_yaw = self._pose_at(
                phase, phase_progress, step, elapsed_s
            )
            reachy_mini.set_target(head=head, antennas=antennas, body_yaw=body_yaw)

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
            return self.SILENT_PHASE_DURATIONS_S[phase] + padding

        path = self.SOUNDS_DIR / sound
        if not path.is_file():
            raise FileNotFoundError(f"Sound for phase {phase!r} not found: {path}")

        return sf.info(str(path)).duration + padding

    def _phase_at(self, elapsed_s: float) -> tuple[str, float]:
        """Return the running phase and the progress within it.

        Args:
            elapsed_s: Seconds since the gesture started.

        Returns:
            (phase name, local progress from 0 to 1).
        """
        phase_start = 0.0
        for phase, phase_end in self.phase_ends_s.items():
            if elapsed_s < phase_end:
                return phase, (elapsed_s - phase_start) / (phase_end - phase_start)
            phase_start = phase_end

        # elapsed_s can overshoot the last phase by a fraction of a tick.
        return list(self.phase_ends_s)[-1], 1.0

    def _play_phase_sound(self, reachy_mini: ReachyMini, phase: str) -> None:
        """Play the sound a phase starts with, if it has one."""
        sound = self.PHASE_SOUNDS[phase]
        if sound is not None:
            self.play_sound(reachy_mini, self.SOUNDS_DIR / sound)


class LibraryMove(Move):
    """Plays a named move from a recorded-moves library.

    Works with any Hugging Face dataset of recorded moves -- Pollen's own
    emotion library, or one you recorded in Marionette.
    """

    def __init__(self, move_name: str, library: RecordedMoves) -> None:
        """
        Args:
            move_name: Name of the move in the library.
            library: The library to load it from.
        """
        self.move_name = move_name
        self._library = library

    def sound_paths(self) -> list[Path]:
        # The recording carries its own sound, played by the SDK itself.
        return []

    def _perform(self, reachy_mini: ReachyMini) -> None:
        reachy_mini.play_move(self._library.get(self.move_name), sound=True)
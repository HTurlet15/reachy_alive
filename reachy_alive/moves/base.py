"""Base class for every discrete gesture the robot can play.

Playing a move goes through three steps:

1. Its sounds are uploaded to the robot -- ahead of time if ``prepare``
   was called, otherwise right before the gesture.
2. The gesture itself runs -- this is ``_perform``, written by each move.
3. The robot returns to neutral, so the next behavior starts from a known
   pose.

To write a move, subclass ``Move`` and implement ``_perform`` and
``sound_paths`` -- the latter returns an empty list if the move plays no
sound. 

Play sounds with ``play_sound``; ``yawning.py`` is the reference.
A move recorded in a Hugging Face dataset needs no code at all -- wrap it
in ``LibraryMove``.
"""

from abc import ABC, abstractmethod
from pathlib import Path

from reachy_mini import ReachyMini
from reachy_mini.motion.recorded_move import RecordedMoves
from reachy_mini.utils import create_head_pose

# The SDK's own neutral is offset ~10° off vertical, not [0.0, 0.0] --
# straight up is where antennas jitter (upstream hardware limit).
NEUTRAL_ANTENNAS_RAD = [-0.1745, 0.1745]


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
        """Move the robot to the neutral head and antenna pose.

        Interpolated, so it's safe from any starting pose. Call it yourself
        mid-gesture if returning to neutral is part of the choreography.

        Args:
            reachy_mini: Connected robot instance.
            duration: Movement duration in seconds. Defaults to RETURN_DURATION_S.
        """
        reachy_mini.goto_target(
            head=create_head_pose(),
            antennas=NEUTRAL_ANTENNAS_RAD,
            duration=duration or self.RETURN_DURATION_S,
        )


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
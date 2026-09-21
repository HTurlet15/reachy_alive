"""Base class for every discrete gesture the robot can play.

Playing a move goes through three steps:

1. Its sounds are uploaded to the robot, while it's still at rest.
2. The gesture itself runs -- this is ``_perform``, written by each move.
3. The robot returns to neutral, so the next behavior starts from a known
   pose.

To write a move, subclass ``Move`` and implement ``_perform``. If it plays
sounds, also override ``sound_paths`` and play them with ``play_sound``;
``yawning.py`` is the reference. A move recorded in a Hugging Face dataset
needs no code at all -- wrap it in ``LibraryMove``.
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

    Subclasses implement ``_perform``. Callers only ever use ``play``,
    which handles everything around the gesture: uploading sounds before
    it, and returning to neutral after it.
    """

    RETURN_DURATION_S = 0.5
    SOUNDS_DIR = Path(__file__).resolve().parent.parent / "assets" / "sounds"

    def play(self, reachy_mini: ReachyMini) -> None:
        """Upload this move's sounds, play it, then return to neutral.

        Args:
            reachy_mini: Connected robot instance.
        """
        self._remote_sounds = self._upload_sounds(reachy_mini)
        self._perform(reachy_mini)
        self.go_neutral(reachy_mini)

    @abstractmethod
    def _perform(self, reachy_mini: ReachyMini) -> None:
        """Play the gesture itself. Free to end on any pose.

        Args:
            reachy_mini: Connected robot instance.
        """

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

    def sound_paths(self) -> list[Path]:
        """List the local sound files this move plays.

        Override this if your move plays sounds, so they get uploaded
        before it starts. The default is none.

        Returns:
            Paths of the move's sound files.
        """
        return []

    def play_sound(self, reachy_mini: ReachyMini, path: Path) -> None:
        """Play one of this move's sounds.

        Uses the copy already on the robot when there is one, so nothing is
        uploaded mid-gesture. Falls back to the local file otherwise.

        Args:
            reachy_mini: Connected robot instance.
            path: Local path of the sound, as listed in ``sound_paths``.
        """
        # Set by play(). getattr rather than a default in __init__, because
        # subclasses define their own __init__ without calling this one.
        remote = getattr(self, "_remote_sounds", {})
        reachy_mini.media.play_sound(remote.get(str(path), str(path)))

    def _upload_sounds(self, reachy_mini: ReachyMini) -> dict[str, str]:
        """Upload this move's sounds while the robot is still at rest.

        On Wireless, playing a local file first uploads it over HTTP, which
        blocks long enough to freeze a gesture. Uploading here moves that
        delay to before the motion, where it can't be seen.

        This runs on every play rather than once at startup: the robot
        stores uploads by file name only, and two moves may ship a sound
        with the same name (``yawning/exhale.wav``, ``stretching/exhale.wav``).
        Re-uploading just before playing guarantees the right one is there.

        Returns:
            Local path -> path on the robot. Empty on the local backend
            (simulation, Lite), which reads files directly.
        """
        audio = reachy_mini.media.audio
        if not hasattr(audio, "upload_sound"):
            return {}
        return {str(path): audio.upload_sound(str(path)) for path in self.sound_paths()}


class LibraryMove(Move):
    """Plays a named move from a recorded-moves library.

    Works with any Hugging Face dataset of recorded moves -- Pollen's own
    emotion library, or one you recorded in Marionette. The recording
    carries its own sound, so there's nothing to upload.
    """

    def __init__(self, move_name: str, library: RecordedMoves) -> None:
        """
        Args:
            move_name: Name of the move in the library.
            library: The library to load it from.
        """
        self.move_name = move_name
        self._library = library

    def _perform(self, reachy_mini: ReachyMini) -> None:
        reachy_mini.play_move(self._library.get(self.move_name), sound=True)
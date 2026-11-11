"""SoundPlayer: starts the robot's sounds in its own thread."""

import logging
import queue
import threading
from pathlib import Path

from reachy_mini import ReachyMini

logger = logging.getLogger(__name__)


class SoundPlayer:
    """Starts each sound it is handed, in its own thread, one after the other.

    The robot's play_sound() returns only once the sound has started: 20 to
    45 ms on the robot, 55 to 85 ms from a laptop, which waits for the
    daemon's answer over the network (issue #82). Called from the control
    loop, it froze the robot that long. Here, play() only drops the sound in
    a queue, and this thread makes the call.

    One thread for every sound keeps them in order, and never calls
    play_sound() twice at once: on the robot, each call replaces the audio
    pipeline the previous one built.
    """

    def __init__(self, reachy_mini: ReachyMini, robot_sounds: dict[Path, str]) -> None:
        """Keep the robot, and where it finds each sound.

        Args:
            reachy_mini: Connected robot instance.
            robot_sounds: What the robot's play_sound() takes for each sound,
                as upload_sounds() made it.
        """
        self._reachy_mini = reachy_mini
        self._robot_sounds = robot_sounds
        # The sounds to start, in order; None tells the thread to stop.
        self._sounds_to_start: queue.Queue[Path | None] = queue.Queue()
        self._thread = threading.Thread(target=self._run, name="SoundPlayer", daemon=True)

    def start(self) -> None:
        """Start the thread that plays the sounds."""
        self._thread.start()

    def play(self, sound: Path) -> None:
        """Have the robot start sound as soon as the thread can, without waiting."""
        self._sounds_to_start.put(sound)

    def stop(self) -> None:
        """Let the thread finish the sound it is starting, then end it.

        Waits one second at most: from a laptop, a call can hang on the
        network much longer. The thread is a daemon, so it never keeps the
        app alive.
        """
        self._sounds_to_start.put(None)
        self._thread.join(timeout=1.0)

    def _run(self) -> None:
        """Start each sound in the queue, until told to stop.

        A sound that fails is logged and skipped: the robot goes on without
        it, rather than stopping over one missing sound.
        """
        while (sound := self._sounds_to_start.get()) is not None:
            try:
                self._reachy_mini.media.play_sound(self._robot_sounds[sound])
            except Exception:
                logger.exception("Could not play %s", sound.name)

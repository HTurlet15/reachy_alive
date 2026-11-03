"""The moves' sounds, made playable by the robot once, when the app starts.

When the app runs on the robot, the robot plays a sound straight from its
own disk. When it runs on a laptop against a Wireless robot, the robot can't
read the laptop's disk: each file is uploaded first, and played from its
copy. The daemon keeps that copy in /tmp/reachy_mini_sounds/, named after the
file, until it restarts (its routers/media.py, SDK 1.13): no two of our
sounds may share a file name, which a test checks.
"""

import logging
import time
from pathlib import Path

from reachy_mini import ReachyMini

from reachy_alive.moves.base import Move

logger = logging.getLogger(__name__)


def upload_sounds(moves: list[Move], reachy_mini: ReachyMini) -> dict[Path, str]:
    """Return what the robot's play_sound() takes, for every sound of every move.

    Uploads each sound first when the app runs on a laptop. A failed upload
    stops the app: it can't play its moves without their sounds.

    Args:
        moves: Every move the app may play.
        reachy_mini: Connected robot instance.

    Returns:
        The robot's path for each local sound file.
    """
    audio = reachy_mini.media.audio
    robot_reads_our_files = not hasattr(audio, "upload_sound")
    started_at = time.monotonic()

    robot_sounds = {}
    for move in moves:
        for cue in move.sound_cues:
            if robot_reads_our_files:
                robot_sounds[cue.path] = str(cue.path)
                continue
            try:
                robot_sounds[cue.path] = audio.upload_sound(str(cue.path))
            except Exception:
                logger.error("Could not upload %s, a sound of %s", cue.path.name, move.name)
                raise

    logger.info("%d sounds ready in %.1f s", len(robot_sounds), time.monotonic() - started_at)
    return robot_sounds

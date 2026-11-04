"""Commands the ActionSelector hands to RobotController, one per tick.

Decision-makers propose; the ActionSelector turns the chosen proposal into
a command; RobotController executes it, and is the only one to drive the
robot.
"""

from dataclasses import dataclass
from pathlib import Path

import numpy as np

from reachy_alive.moves.base import Move


@dataclass(frozen=True)
class RobotCommand:
    """What the robot does on one tick: a pose, and the sounds to start.

    An order: the ActionSelector builds one per tick, and the RobotController
    carries it out once, right away, then drops it. A sound is put in the
    command only on the tick it is due, so the controller starts every sound
    it receives at once. What was sent is kept as a CommandedPose.

    Attributes:
        head: 4x4 head pose matrix.
        antennas: Antenna angles, in radians.
        body_yaw: Body yaw, in radians; None leaves the body where it is.
        sounds: Local paths of the sounds to start this tick.
        from_move: Whether the pose belongs to a move, its way back to
            neutral included, rather than to breathing.
    """

    head: np.ndarray
    antennas: np.ndarray
    body_yaw: float | None = None
    sounds: tuple[Path, ...] = ()
    from_move: bool = False


@dataclass(frozen=True)
class PlayMove:
    """Play a discrete move to completion.

    Transitional: this command exists because Move.play() blocks the
    control loop. Once moves run tick by tick, they will return a pose
    each tick like breathing does, and this command will go away.

    Attributes:
        move: The move to play.
    """

    move: Move


# Anything a decision-maker can return for one tick.
Command = RobotCommand | PlayMove

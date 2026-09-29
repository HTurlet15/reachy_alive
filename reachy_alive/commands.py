"""Commands the decision layer hands to RobotController for execution.

Decision-makers (IdleManager today, an arbiter or a behavior tree later)
return one of these each tick instead of driving the robot themselves.
RobotController reads the command and executes it.
"""

from dataclasses import dataclass

import numpy as np

from reachy_alive.moves.base import Move


@dataclass(frozen=True)
class HoldPose:
    """Hold a pose for the current tick.

    Attributes:
        head: 4x4 head pose matrix.
        antennas: Antenna angles, in radians.
    """

    head: np.ndarray
    antennas: np.ndarray


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
Command = HoldPose | PlayMove
# reachy_alive/brainstem/custom_behaviors/base_behavior.py
"""Common interface for discrete, one-off idle gestures."""

from abc import ABC, abstractmethod

from reachy_mini import ReachyMini


class CustomMove(ABC):
    """Interface for a discrete idle gesture (yawn, stretch, look around).

    Unlike breathing (a continuous pure function), these behaviors are
    one-off actions: triggered once, they run to completion, then
    control returns to breathing as the default idle state.
    """

    @abstractmethod
    def trigger(self, reachy_mini: ReachyMini) -> None:
        """Play this gesture on the robot.

        Args:
            reachy_mini: Connected robot instance.
        """
        raise NotImplementedError
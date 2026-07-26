# reachy_alive/brainstem/robot_manager.py
"""Robot control loop execution."""

import time
from typing import Callable

from reachy_mini import ReachyMini

from reachy_alive.brainstem.idle_manager import IdleManager
from reachy_alive.shared_state import SharedState


class RobotManager:
    """Runs the control loop and sends commands to the physical robot.

    This is the only class that calls ReachyMini directly. It makes no
    decisions of its own about what to play -- it reads IdleManager's
    decision each tick and executes it.

    Attributes:
        idle_manager: Supplies the idle pose for each tick.
        tick_period_s: Time, in seconds, between control loop ticks.
    """

    def __init__(self, idle_manager: IdleManager, tick_hz: float = 20.0) -> None:
        """
        Args:
            idle_manager: The IdleManager instance to query each tick.
            tick_hz: Control loop frequency, in Hz.
        """
        self.idle_manager = idle_manager
        self.tick_period_s = 1.0 / tick_hz

    def run(
        self,
        reachy_mini: ReachyMini,
        shared_state: SharedState,
        stop_event,
        get_antennas_enabled: Callable[[], bool],
    ) -> None:
        """Run the control loop until stop_event is set.

        Args:
            reachy_mini: Connected robot instance.
            shared_state: Shared blackboard, passed through to IdleManager.
            stop_event: Set externally (e.g. on Ctrl+C) to terminate the loop.
            get_antennas_enabled: Returns whether antennas should move.
        """
        t0 = time.time()
        while not stop_event.is_set():
            t = time.time() - t0

            pose = self.idle_manager.get_pose(
                t, shared_state, antennas_enabled=get_antennas_enabled()
            )
            if pose is not None:
                head_pose, antennas_rad = pose
                reachy_mini.set_target(head=head_pose, antennas=antennas_rad)

            time.sleep(self.tick_period_s)
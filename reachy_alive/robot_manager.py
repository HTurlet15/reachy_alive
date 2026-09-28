import time
from typing import Callable

from reachy_mini import ReachyMini

from reachy_alive.brainstem.idle_manager import IdleManager
from reachy_alive.commands import Command, HoldPose, PlayMove
from reachy_alive.shared_state import SharedState


class RobotManager:
    """Runs the control loop and executes the commands it receives.

    It makes no decisions of its own: each tick, it asks IdleManager for a
    command and carries it out. Decision-makers never drive the robot.
    Moves do talk to the robot, but only while RobotManager executes a
    PlayMove, from this loop's thread.

    Attributes:
        idle_manager: Supplies a command for each tick.
        tick_period_s: Time, in seconds, between control loop ticks.
    """

    def __init__(self, idle_manager: IdleManager, tick_hz: float = 50.0) -> None:
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
        reachy_mini.enable_motors()
        reachy_mini.wake_up()

        try:
            t0 = time.monotonic()
            while not stop_event.is_set():
                t = time.monotonic() - t0
                command = self.idle_manager.decide(
                    t, shared_state, reachy_mini, antennas_enabled=get_antennas_enabled()
                )
                self._execute(command, reachy_mini)
                time.sleep(self.tick_period_s)
        finally:
            reachy_mini.goto_sleep()
            reachy_mini.disable_motors()

    def _execute(self, command: Command, reachy_mini: ReachyMini) -> None:
        """Carry out one command on the robot.

        Args:
            command: The command to execute.
            reachy_mini: Connected robot instance.

        Raises:
            TypeError: If the command type is unknown.
        """
        if isinstance(command, HoldPose):
            reachy_mini.set_target(head=command.head, antennas=command.antennas)
        elif isinstance(command, PlayMove):
            command.move.play(reachy_mini)
        else:
            raise TypeError(f"Unknown command: {command!r}")
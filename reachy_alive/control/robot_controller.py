import time

from reachy_mini import ReachyMini

from reachy_alive.control.action_selector import ActionSelector
from reachy_alive.control.commands import Command, HoldPose, PlayMove
from reachy_alive.shared_state import SharedState


class RobotController:
    """Runs the control loop and executes the commands it receives.

    It makes no decisions of its own: each tick, it asks the ActionSelector
    for a command and carries it out. It also records in SharedState when a
    move ends, whoever asked for it. Decision-makers never drive the
    robot. Moves do talk to the robot, but only while RobotController executes
    a PlayMove, from this loop's thread.

    Attributes:
        action_selector: Chooses the command for each tick.
        tick_period_s: Time, in seconds, between control loop ticks.
    """

    def __init__(self, action_selector: ActionSelector, tick_hz: float = 50.0) -> None:
        """
        Args:
            action_selector: Chooses the command for each tick.
            tick_hz: Control loop frequency, in Hz.
        """
        self.action_selector = action_selector
        self.tick_period_s = 1.0 / tick_hz

    def run(self, reachy_mini: ReachyMini, shared_state: SharedState, stop_event) -> None:
        """Run the control loop until stop_event is set.

        Args:
            reachy_mini: Connected robot instance.
            shared_state: Shared blackboard. Passed to the ActionSelector,
                and updated when a move ends.
            stop_event: Set externally (e.g. on Ctrl+C) to terminate the loop.
        """
        reachy_mini.enable_motors()
        reachy_mini.wake_up()

        try:
            t0 = time.monotonic()
            while not stop_event.is_set():
                t = time.monotonic() - t0
                command = self.action_selector.decide(t, shared_state, reachy_mini)
                self._execute(command, reachy_mini, shared_state)
                time.sleep(self.tick_period_s)
        finally:
            reachy_mini.goto_sleep()
            reachy_mini.disable_motors()

    def _execute(
        self, command: Command, reachy_mini: ReachyMini, shared_state: SharedState
    ) -> None:
        """Carry out one command on the robot, recording when a move ends.

        Args:
            command: The command to execute.
            reachy_mini: Connected robot instance.
            shared_state: Shared blackboard, updated when a move ends.

        Raises:
            TypeError: If the command type is unknown.
        """
        if isinstance(command, HoldPose):
            reachy_mini.set_target(head=command.head, antennas=command.antennas)
        elif isinstance(command, PlayMove):
            command.move.play(reachy_mini)
            shared_state.mark_activity()
        else:
            raise TypeError(f"Unknown command: {command!r}")
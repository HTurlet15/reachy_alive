"""RobotController: the control loop, the only part of the app that drives the robot."""

import time

from reachy_mini import ReachyMini

from reachy_alive.control.action_selector import ActionSelector
from reachy_alive.control.commands import Command, HoldPose, PlayMove
from reachy_alive.shared_state import CommandedPose, SharedState


class RobotController:
    """Runs the control loop and executes the commands it receives.

    It makes no decisions of its own: each tick, it asks the ActionSelector
    for a command and carries it out. It records in SharedState each pose it
    sends (its efference copy), and when a move plays and ends, whoever asked
    for it, waking up and going to sleep included. Decision-makers never
    drive the robot. Moves do talk to the robot, but only while
    RobotController executes a PlayMove, from this loop's thread.
    """

    TICK_HZ = 50.0

    def __init__(self, action_selector: ActionSelector) -> None:
        """Keep the selector.

        Args:
            action_selector: Chooses the command for each tick.
        """
        self.action_selector = action_selector

    def run(self, reachy_mini: ReachyMini, shared_state: SharedState, stop_event) -> None:
        """Run the control loop until stop_event is set.

        Args:
            reachy_mini: Connected robot instance.
            shared_state: Shared blackboard. Passed to the ActionSelector,
                and updated with what the robot is sent and does.
            stop_event: Set externally (e.g. on Ctrl+C) to terminate the loop.
        """
        reachy_mini.enable_motors()
        shared_state.set_move_playing(True)
        try:
            reachy_mini.wake_up()
        finally:
            shared_state.set_move_playing(False)

        try:
            t0 = time.monotonic()
            while not stop_event.is_set():
                t = time.monotonic() - t0
                command = self.action_selector.decide(t, shared_state, reachy_mini)
                self._execute(command, reachy_mini, shared_state)
                time.sleep(1.0 / self.TICK_HZ)
        finally:
            shared_state.set_move_playing(True)
            reachy_mini.goto_sleep()
            reachy_mini.disable_motors()

    def _execute(
        self, command: Command, reachy_mini: ReachyMini, shared_state: SharedState
    ) -> None:
        """Carry out one command on the robot, recording what it sends."""
        if isinstance(command, HoldPose):
            reachy_mini.set_target(head=command.head, antennas=command.antennas)
            shared_state.record_commanded_pose(
                CommandedPose(at=time.monotonic(), head=command.head, antennas=command.antennas)
            )
        elif isinstance(command, PlayMove):
            shared_state.set_move_playing(True)
            try:
                command.move.play(reachy_mini)
            finally:
                shared_state.set_move_playing(False)
            shared_state.mark_activity()
        else:
            raise TypeError(f"Unknown command: {command!r}")

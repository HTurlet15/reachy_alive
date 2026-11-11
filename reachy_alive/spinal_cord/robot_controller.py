"""RobotController: the control loop, the only part of the app that drives the robot."""

import logging
import time

from reachy_mini import ReachyMini
from websockets.exceptions import ConnectionClosed

from reachy_alive.brain.basal_ganglia.action_selector import ActionSelector
from reachy_alive.shared_state import CommandedPose, SharedState
from reachy_alive.spinal_cord.commands import RobotCommand
from reachy_alive.spinal_cord.sound_player import SoundPlayer

logger = logging.getLogger(__name__)


class RobotController:
    """Runs the control loop and executes the commands it receives.

    It makes no decisions of its own: each tick, it asks the ActionSelector
    for a command and carries it out. It records in SharedState each pose it
    sends (its efference copy), and when a move plays and ends, whoever asked
    for it, waking up and going to sleep included. It also hands each command's
    sounds to its SoundPlayer, which starts them without making the loop
    wait: with it, it is the only part that talks to the robot.

    Each tick is due at a fixed time, every TICK_S. A tick that runs late is
    followed at once by the next one, never by a burst catching up: the
    slots already gone are skipped, and logged.
    """

    TICK_HZ = 50.0
    TICK_S = 1.0 / TICK_HZ

    def __init__(self, action_selector: ActionSelector, sound_player: SoundPlayer) -> None:
        """Keep the selector, and what starts the sounds.

        Args:
            action_selector: Chooses the command for each tick.
            sound_player: Starts each command's sounds in its own thread;
                started and stopped with the control loop.
        """
        self.action_selector = action_selector
        self.sound_player = sound_player

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

        self.sound_player.start()
        try:
            tick_due_at = time.monotonic()
            while not stop_event.is_set():
                command = self.action_selector.decide(time.monotonic())
                self._execute(command, reachy_mini, shared_state)
                tick_due_at = self._wait_for_next_tick(tick_due_at + self.TICK_S)
        finally:
            # Before going to sleep, which plays its own sound.
            self.sound_player.stop()
            shared_state.set_move_playing(True)
            # With the connection to the daemon lost, both calls fail too: one
            # log line, so the error that stopped the loop stays the last printed.
            # The SDK reports a lost connection two ways: ConnectionError once it
            # has noticed (about 1 s), ConnectionClosed from websockets before.
            try:
                reachy_mini.goto_sleep()
                reachy_mini.disable_motors()
            except (ConnectionError, ConnectionClosed):
                logger.warning(
                    "Could not put the robot to sleep: the connection to the daemon is lost"
                )

    def _execute(
        self, command: RobotCommand, reachy_mini: ReachyMini, shared_state: SharedState
    ) -> None:
        """Start the command's sounds, send its pose, and record both what it sent and why."""
        # Each sound is due now: it is only in the command on its tick.
        for sound in command.sounds:
            self.sound_player.play(sound)
        reachy_mini.set_target(
            head=command.head, antennas=command.antennas, body_yaw=command.body_yaw
        )
        shared_state.record_commanded_pose(
            CommandedPose(
                at=time.monotonic(),
                head=command.head,
                antennas=command.antennas,
                body_yaw=command.body_yaw,
            )
        )
        self._record_whether_a_move_plays(command.from_move, shared_state)

    @staticmethod
    def _record_whether_a_move_plays(from_move: bool, shared_state: SharedState) -> None:
        """Record when a move starts and ends, as the senses need to know."""
        if from_move != shared_state.is_move_playing():
            shared_state.set_move_playing(from_move)

    def _wait_for_next_tick(self, due_at: float) -> float:
        """Sleep until the next tick is due, and return when it was due.

        Skips, and logs, the slots that went by while this tick ran late.
        """
        now = time.monotonic()
        if now < due_at:
            time.sleep(due_at - now)
            return due_at

        late_s = now - due_at
        skipped_ticks = int(late_s // self.TICK_S)
        if skipped_ticks:
            logger.warning("Skipped %d ticks (%.0f ms late)", skipped_ticks, late_s * 1000)
        return due_at + skipped_ticks * self.TICK_S

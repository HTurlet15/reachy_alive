import logging
import queue
import threading

from reachy_mini import ReachyMini, ReachyMiniApp
from reachy_mini.motion.recorded_move import RecordedMoves

from reachy_alive.control.action_selector import ActionSelector
from reachy_alive.brain.brainstem.idle_manager import IdleManager
from reachy_alive.moves.base import LibraryMove, Move
from reachy_alive.moves.sneezing import Sneezing
from reachy_alive.moves.stretching import Stretching
from reachy_alive.moves.yawning import Yawning
from reachy_alive.control.robot_controller import RobotController
from reachy_alive.routes import create_router
from reachy_alive.shared_state import SharedState

class ReachyAlive(ReachyMiniApp):
    custom_app_url: str | None = "http://0.0.0.0:8042"
    request_media_backend: str | None = None

    def run(self, reachy_mini: ReachyMini, stop_event: threading.Event):
        """Build every part of the app, wire them together, and run the loop.

        Called by the SDK once the robot is connected. Blocks until
        stop_event is set.

        Args:
            reachy_mini: Connected robot instance.
            stop_event: Set by the SDK to stop the app.
        """
        # Facts shared across threads: the idle timer, the page's settings.
        shared_state = SharedState()

        # The moves idle picks from. The page can play the same moves, looked
        # up by name, so two moves must never share one.
        idle_moves = self._build_idle_moves()
        idle_moves_by_name = {move.name: move for move in idle_moves}
        if len(idle_moves_by_name) != len(idle_moves):
            raise ValueError("Two moves share the same name")

        # The page's routes run in the web server's thread: they only drop
        # requested moves in this queue and read or change shared_state,
        # never touching the robot.
        move_requests: queue.Queue[Move] = queue.Queue()
        self.settings_app.include_router(
            create_router(idle_moves_by_name, move_requests, shared_state)
        )

        # Decide, choose, execute: IdleManager proposes, ActionSelector picks
        # a requested move over idle, RobotController drives the robot.
        idle_manager = IdleManager(idle_moves)
        action_selector = ActionSelector(idle_manager, move_requests)
        robot_controller = RobotController(action_selector)

        # The control loop, in this thread, until the app stops.
        robot_controller.run(reachy_mini, shared_state, stop_event)
    def _build_idle_moves(self) -> list[Move]:
        """Build the moves the idle manager picks from.

        Raises:
            ValueError: If a configured library move doesn't exist.
        """
        pollen_emotions = RecordedMoves("pollen-robotics/reachy-mini-emotions-library")
        reachy_alive_recordings = RecordedMoves("HTurlet15/reachy-alive")

        # Recorded by Pollen, played as-is. Excludes waiting, mini-deep-sleep
        # and toc-toc-toc, which wedge the IK solver (pollen-robotics/reachy_mini#1417).
        
        pollen_moves = self._library_moves(pollen_emotions, [
            "boredom1", "tired1", "serenity1", "curious1", "lonely1",
        ])

        # Recorded by hand in Marionette, played as-is.
        marionette_moves = self._library_moves(reachy_alive_recordings, [
            "hiccup-full",
        ])

        # Written entirely in code.
        coded_moves = [Stretching(), Yawning()]

        # Recorded head, coded antennas.
        mixed_moves = [Sneezing(reachy_alive_recordings)]

        return pollen_moves + marionette_moves + coded_moves + mixed_moves

    def _library_moves(self, library: RecordedMoves, names: list[str]) -> list[Move]:
        """Wrap named moves from a library, checking they all exist.

        Args:
            library: The recorded-moves library to load from.
            names: Move names to wrap.

        Returns:
            One LibraryMove per name.

        Raises:
            ValueError: If a name isn't in the library.
        """
        available = library.list_moves()
        missing = [name for name in names if name not in available]
        if missing:
            raise ValueError(f"Moves not found in library: {missing}")
        return [LibraryMove(name, library) for name in names]


if __name__ == "__main__":
    # Run directly, this script is the program, and nothing else sets up
    # logging: show this app's info logs, and warnings from everything else.
    logging.basicConfig(format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    logging.getLogger("reachy_alive").setLevel(logging.INFO)

    app = ReachyAlive()
    try:
        app.wrapped_run()
    except KeyboardInterrupt:
        app.stop()
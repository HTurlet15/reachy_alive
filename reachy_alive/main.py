import logging
import queue
import threading

from fastapi import HTTPException
from pydantic import BaseModel, Field
from reachy_mini import ReachyMini, ReachyMiniApp
from reachy_mini.motion.recorded_move import RecordedMoves

from reachy_alive.action_selector import ActionSelector
from reachy_alive.brainstem.idle_manager import IdleManager
from reachy_alive.moves.base import LibraryMove, Move
from reachy_alive.moves.sneezing import Sneezing
from reachy_alive.moves.stretching import Stretching
from reachy_alive.moves.yawning import Yawning
from reachy_alive.robot_controller import RobotController
from reachy_alive.shared_state import SharedState

# Below this, the robot barely breathes between idle moves; above, the page
# would look broken.
MIN_IDLE_MOVE_INTERVAL_S = 5.0
MAX_IDLE_MOVE_INTERVAL_S = 600.0


class IdleMoveInterval(BaseModel):
    """Seconds to wait between two idle moves, as the app's page sends them."""

    min_s: float = Field(ge=MIN_IDLE_MOVE_INTERVAL_S, le=MAX_IDLE_MOVE_INTERVAL_S)
    max_s: float = Field(ge=MIN_IDLE_MOVE_INTERVAL_S, le=MAX_IDLE_MOVE_INTERVAL_S)


class ReachyAlive(ReachyMiniApp):
    custom_app_url: str | None = "http://0.0.0.0:8042"
    request_media_backend: str | None = None

    def run(self, reachy_mini: ReachyMini, stop_event: threading.Event):
        shared_state = SharedState()

        idle_moves = self._build_idle_moves()
        idle_moves_by_name = {move.name: move for move in idle_moves}
        if len(idle_moves_by_name) != len(idle_moves):
            raise ValueError("Two moves share the same name")
        move_requests: queue.Queue[Move] = queue.Queue()
        self._register_move_routes(idle_moves_by_name, move_requests)
        self._register_settings_routes(shared_state)

        idle_manager = IdleManager(idle_moves)
        action_selector = ActionSelector(idle_manager, move_requests)
        robot_controller = RobotController(action_selector)

        robot_controller.run(reachy_mini, shared_state, stop_event)

    def _register_move_routes(
        self, moves_by_name: dict[str, Move], move_requests: queue.Queue
    ) -> None:
        """Register the routes that list moves and request one.

        Args:
            moves_by_name: Every move the robot can play, by name.
            move_requests: Where requested moves wait to be played.
        """

        @self.settings_app.get("/moves")
        def list_moves() -> list[str]:
            return sorted(moves_by_name)

        @self.settings_app.post("/moves/{name}/play", status_code=202)
        def request_move(name: str) -> dict[str, str]:
            if name not in moves_by_name:
                raise HTTPException(status_code=404, detail=f"Unknown move: {name}")
            move_requests.put(moves_by_name[name])
            return {"requested": name}

    def _register_settings_routes(self, shared_state: SharedState) -> None:
        """Register the routes that read and change the app's settings.

        Args:
            shared_state: Where the settings live.
        """

        @self.settings_app.get("/settings/idle-move-interval")
        def get_idle_move_interval() -> IdleMoveInterval:
            min_s, max_s = shared_state.idle_move_interval_range_s()
            return IdleMoveInterval(min_s=min_s, max_s=max_s)

        @self.settings_app.put("/settings/idle-move-interval")
        def set_idle_move_interval(interval: IdleMoveInterval) -> IdleMoveInterval:
            if interval.min_s > interval.max_s:
                raise HTTPException(status_code=422, detail="min_s must not exceed max_s")
            shared_state.set_idle_move_interval_range_s(interval.min_s, interval.max_s)
            return interval

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
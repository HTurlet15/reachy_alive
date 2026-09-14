import threading

from pydantic import BaseModel
from typing import Callable
from reachy_mini import ReachyMini, ReachyMiniApp
from reachy_mini.motion.recorded_move import RecordedMoves

from reachy_alive.brainstem.idle_manager import IdleManager
from reachy_alive.moves.base import LibraryMove, Move
from reachy_alive.moves.stretching import Stretching
from reachy_alive.moves.yawning import Yawning
from reachy_alive.robot_manager import RobotManager
from reachy_alive.shared_state import SharedState

class ReachyAlive(ReachyMiniApp):
    custom_app_url: str | None = "http://0.0.0.0:8042"
    request_media_backend: str | None = None

    def run(self, reachy_mini: ReachyMini, stop_event: threading.Event):
        get_antennas_enabled = self._register_settings_routes()

        shared_state = SharedState()
        idle_manager = IdleManager(self._build_idle_behaviors())
        robot_manager = RobotManager(idle_manager)

        robot_manager.run(
            reachy_mini,
            shared_state,
            stop_event,
            get_antennas_enabled=get_antennas_enabled,
        )

    def _register_settings_routes(self) -> Callable[[], bool]:
        """Register the settings API routes.

        Returns:
            A getter for the current antennas-enabled state.
        """
        antennas_enabled = True

        class AntennaState(BaseModel):
            enabled: bool

        @self.settings_app.post("/antennas")
        def update_antennas_state(state: AntennaState):
            nonlocal antennas_enabled
            antennas_enabled = state.enabled
            return {"antennas_enabled": antennas_enabled}

        return lambda: antennas_enabled

    def _build_idle_behaviors(self) -> list[Move]:
        """Build the discrete gestures the idle manager picks from.

        Raises:
            ValueError: If a configured move is missing from the library.
        """
        emotions = RecordedMoves("pollen-robotics/reachy-mini-emotions-library")

        # Closest available stand-ins for an idle, slightly-bored robot
        #
        # WORKAROUND (Reachy Mini SDK v1.10.0): 
        # Explicitly excluding "waiting", "mini-deep-sleep", and "toc-toc-toc". 
        # These specific recorded moves park the head outside the physical workspace 
        # limit (z < -175mm). This wedges the Inverse Kinematics (IK) solver in an 
        # unrecoverable collision state. Once wedged, the SDK silently swallows 
        # subsequent target commands (returning valid UUIDs and playing audio, 
        # but executing no motion) until the daemon process is fully restarted.
        library_move_names = ["boredom1", "boredom2", "tired1"]

        missing = [name for name in library_move_names if name not in emotions.list_moves()]
        if missing:
            raise ValueError(f"Moves not found in emotions library: {missing}")

        return [
            LibraryMove(name, emotions) for name in library_move_names
        ] + [Stretching(), Yawning()]


if __name__ == "__main__":
    app = ReachyAlive()
    try:
        app.wrapped_run()
    except KeyboardInterrupt:
        app.stop()
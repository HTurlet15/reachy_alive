# reachy_alive/main.py
import threading

from pydantic import BaseModel
from reachy_mini import ReachyMini, ReachyMiniApp

from reachy_alive.brainstem.idle_manager import IdleManager
from reachy_alive.brainstem.robot_manager import RobotManager
from reachy_alive.shared_state import SharedState


class ReachyAlive(ReachyMiniApp):
    custom_app_url: str | None = "http://0.0.0.0:8042"
    request_media_backend: str | None = None

    def run(self, reachy_mini: ReachyMini, stop_event: threading.Event):
        antennas_enabled = True

        class AntennaState(BaseModel):
            enabled: bool

        @self.settings_app.post("/antennas")
        def update_antennas_state(state: AntennaState):
            nonlocal antennas_enabled
            antennas_enabled = state.enabled
            return {"antennas_enabled": antennas_enabled}

        shared_state = SharedState()
        idle_manager = IdleManager()
        robot_manager = RobotManager(idle_manager)

        robot_manager.run(
            reachy_mini,
            shared_state,
            stop_event,
            get_antennas_enabled=lambda: antennas_enabled,
        )


if __name__ == "__main__":
    app = ReachyAlive()
    try:
        app.wrapped_run()
    except KeyboardInterrupt:
        app.stop()
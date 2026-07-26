import threading
from reachy_mini import ReachyMini, ReachyMiniApp
import time
from pydantic import BaseModel

from reachy_alive.brainstem.idle_manager import IdleManager
from reachy_alive.shared_state import SharedState

class ReachyAlive(ReachyMiniApp):
    custom_app_url: str | None = "http://0.0.0.0:8042"
    request_media_backend: str | None = None

    def run(self, reachy_mini: ReachyMini, stop_event: threading.Event):
        t0 = time.time()

        antennas_enabled = True
        sound_play_requested = False
        shared_state = SharedState()
        idle_manager = IdleManager()

        class AntennaState(BaseModel):
            enabled: bool

        @self.settings_app.post("/antennas")
        def update_antennas_state(state: AntennaState):
            nonlocal antennas_enabled
            antennas_enabled = state.enabled
            return {"antennas_enabled": antennas_enabled}

        @self.settings_app.post("/play_sound")
        def request_sound_play():
            nonlocal sound_play_requested
            sound_play_requested = True

        while not stop_event.is_set():
            t = time.time() - t0
            pose = idle_manager.get_pose(t, shared_state, antennas_enabled=antennas_enabled)

            if pose is not None:
                head_pose, antennas_rad = pose
                reachy_mini.set_target(head=head_pose, antennas=antennas_rad)

            time.sleep(0.05)


if __name__ == "__main__":
    app = ReachyAlive()
    try:
        app.wrapped_run()
    except KeyboardInterrupt:
        app.stop()
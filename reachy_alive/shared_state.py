# reachy_alive/shared_state.py
import threading
import time
from typing import Optional


class SharedState:
    """Central, thread-safe blackboard shared across all cognitive modules.

    Cognitive modules (Brainstem, Amygdala, Prefrontal Cortex, etc.) never
    call each other directly; they only read and write this object.

    Attributes:
        lock: Guards all reads/writes to prevent race conditions.
        last_activity_at: Unix timestamp of the last notable activity —
            either IdleManager playing a discrete gesture, or (later) an
            external reaction from Amygdala/Prefrontal Cortex. None means
            nothing notable has happened since startup.
        current_animation_target: Name of a specific move that an external
            module wants played right now. None means nothing external is
            pending. Not written anywhere yet — reserved for Amygdala.
    """

    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.last_activity_at: Optional[float] = None
        # TODO: written by Amygdala once it exists; read by RobotManager.
        self.current_animation_target: Optional[str] = None

    def mark_activity(self) -> None:
        """Record that something notable just happened, resetting the idle timer."""
        with self.lock:
            self.last_activity_at = time.time()

    def seconds_since_last_activity(self) -> float:
        """Time elapsed since the last notable activity.

        Returns:
            Seconds since the last activity, or 0.0 if nothing notable
            has happened yet (e.g. right after startup).
        """
        with self.lock:
            if self.last_activity_at is None:
                return 0.0
            return time.time() - self.last_activity_at
# reachy_alive/shared_state.py
import threading
import time


class SharedState:
    """Central, thread-safe blackboard of state shared across modules.

    It holds facts any module may read at any time, such as when the last
    notable activity happened. It does not carry orders: a module that
    wants something done hands over a command instead (see
    reachy_alive.commands).

    Attributes:
        lock: Guards all reads/writes to prevent race conditions.
        last_activity_at: Monotonic clock reading (time.monotonic()) of when
            the last move ended, written by RobotController whoever asked for
            the move. Starts at the app's launch.
    """

    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.last_activity_at: float = time.monotonic()

    def mark_activity(self) -> None:
        """Record that something notable just happened, resetting the idle timer."""
        with self.lock:
            self.last_activity_at = time.monotonic()

    def seconds_since_last_activity(self) -> float:
        """Time elapsed since the last notable activity, or since the app's launch.

        Returns:
            Seconds since the last activity.
        """
        with self.lock:
            return time.monotonic() - self.last_activity_at
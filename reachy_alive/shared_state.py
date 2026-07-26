# reachy_alive/shared_state.py
import threading
import time
from typing import Optional


class SharedState:
    """Central, thread-safe blackboard shared across all cognitive modules.

    Cognitive modules (Brainstem, Amygdala, Prefrontal Cortex, etc.) never
    call each other directly; they only read and write this object. This
    avoids tight coupling between modules running on independent threads.

    Attributes:
        lock: Guards all reads/writes to prevent race conditions.
        last_external_command_at: Unix timestamp of the last external
            command (an Amygdala reaction or Prefrontal Cortex expression),
            or None if none has occurred yet.
    """

    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.last_external_command_at: Optional[float] = None

    def is_external_active(self, cooldown_s: float = 2.0) -> bool:
        """Check whether an external command is still considered active.

        Args:
            cooldown_s: Duration, in seconds, that an external command
                keeps idle behaviors suppressed after it occurs.

        Returns:
            True if an external command occurred within the cooldown
            window, False otherwise.
        """
        with self.lock:
            if self.last_external_command_at is None:
                return False
            return (time.time() - self.last_external_command_at) < cooldown_s
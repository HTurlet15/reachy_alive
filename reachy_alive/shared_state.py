import threading
import time
from dataclasses import dataclass
import numpy as np

DEFAULT_IDLE_MOVE_INTERVAL_RANGE_S = (20.0, 30.0)

@dataclass(frozen=True)
class CommandedPose:
    """A pose RobotController sent to the robot: its efference copy.

    Attributes:
        at: Monotonic clock reading (time.monotonic()) of when it was sent.
        head: 4x4 head pose matrix.
        antennas: Antenna angles, in radians.
    """

    at: float
    head: np.ndarray
    antennas: np.ndarray

class SharedState:
    """Central, thread-safe blackboard of state shared across modules.

    It holds facts any module may read at any time, such as when the last
    notable activity happened. It does not carry orders: a module that
    wants something done hands over a command instead (see
    reachy_alive.control.commands).

    Attributes:
        lock: Guards all reads/writes to prevent race conditions.
        last_activity_at: Monotonic clock reading (time.monotonic()) of when
            the last move ended, written by RobotController whoever asked for
            the move. Starts at the app's launch.
    """

    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.last_activity_at: float = time.monotonic()
        # Written by the app's page only; read by IdleManager.
        self._idle_move_interval_range_s = DEFAULT_IDLE_MOVE_INTERVAL_RANGE_S
        # Written by RobotController only, around each move it plays.
        self._move_playing = False
        # Written by InertialUnitSense only.
        self._last_bump_at: float | None = None
        # Written by RobotController only, each time it sends a pose.
        self._commanded_pose: CommandedPose | None = None

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

    def set_move_playing(self, playing: bool) -> None:
        """Record whether RobotController is playing a move right now, waking
        the robot up included.

        Args:
            playing: True when a move starts, False once it has ended.
        """
        with self.lock:
            self._move_playing = playing

    def is_move_playing(self) -> bool:
        """Return whether RobotController is playing a move right now."""
        with self.lock:
            return self._move_playing

    def record_bump(self, at: float) -> None:
        """Record a bump felt at `at`, a time.monotonic() reading."""
        with self.lock:
            self._last_bump_at = at

    def last_bump_at(self) -> float | None:
        """Return when the last bump was felt (time.monotonic()), or None if none yet."""
        with self.lock:
            return self._last_bump_at

    def record_commanded_pose(self, pose: CommandedPose) -> None:
        """Record the pose RobotController just sent to the robot."""
        with self.lock:
            self._commanded_pose = pose

    def last_commanded_pose(self) -> CommandedPose | None:
        """Return the last pose RobotController sent, or None if none yet."""
        with self.lock:
            return self._commanded_pose
        
    def idle_move_interval_range_s(self) -> tuple[float, float]:
        """Return the (min, max) seconds to wait between two idle moves."""
        with self.lock:
            return self._idle_move_interval_range_s

    def set_idle_move_interval_range_s(self, min_s: float, max_s: float) -> None:
        """Replace the (min, max) seconds to wait between two idle moves.

        Args:
            min_s: Shortest wait, in seconds.
            max_s: Longest wait, in seconds.

        Raises:
            ValueError: If min_s is negative or greater than max_s.
        """
        if not 0.0 <= min_s <= max_s:
            raise ValueError(f"Invalid idle move interval: ({min_s}, {max_s})")
        with self.lock:
            self._idle_move_interval_range_s = (min_s, max_s)
"""Facts shared across threads: a blackboard any module can read."""

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
    move ended. It does not carry orders: a module that wants something done
    hands over a command instead (see reachy_alive.control.commands).

    Methods are grouped by fact. Each group names its one writer; every
    other module only reads.

    Attributes:
        lock: Guards all reads/writes to prevent race conditions.
        last_activity_at: Monotonic clock reading (time.monotonic()) of when
            the last move ended, whoever asked for the move. Starts at the
            app's launch.
    """

    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.last_activity_at: float = time.monotonic()
        self._move_playing = False
        self._commanded_pose: CommandedPose | None = None
        self._last_bump_at: float | None = None
        self._idle_move_interval_range_s = DEFAULT_IDLE_MOVE_INTERVAL_RANGE_S
        self._antenna_pushed_since: dict[str, float | None] = {"right": None, "left": None}

    # Idle timer. Written by RobotController, when a move ends.

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

    # Efference copy: what the robot is doing itself. Written by
    # RobotController.

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

    def record_commanded_pose(self, pose: CommandedPose) -> None:
        """Record the pose RobotController just sent to the robot."""
        with self.lock:
            self._commanded_pose = pose

    def last_commanded_pose(self) -> CommandedPose | None:
        """Return the last pose RobotController sent, or None if none yet."""
        with self.lock:
            return self._commanded_pose

    # Senses: what the robot perceives. Each fact is written by its sense.

    def record_bump(self, at: float) -> None:
        """Record a bump felt at `at`, a time.monotonic() reading.

        Written by InertialUnitSense.
        """
        with self.lock:
            self._last_bump_at = at

    def last_bump_at(self) -> float | None:
        """Return when the last bump was felt (time.monotonic()), or None if none yet."""
        with self.lock:
            return self._last_bump_at

    def set_antenna_pushed_since(self, side: str, since: float | None) -> None:
        """Record since when an antenna is pushed, or None once it isn't.

        Written by AntennasSense.

        Args:
            side: "right" or "left", the robot's own sides.
            since: When the push started (time.monotonic()), or None.
        """
        with self.lock:
            self._antenna_pushed_since[side] = since

    def antenna_pushed_since(self, side: str) -> float | None:
        """Return since when an antenna is pushed (time.monotonic()), or None if it isn't.

        Args:
            side: "right" or "left", the robot's own sides.
        """
        with self.lock:
            return self._antenna_pushed_since[side]
        
    # Settings. Written by the app's page, through its routes.

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
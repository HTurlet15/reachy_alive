"""Facts shared across threads: a blackboard any module can read."""

import threading
import time
from dataclasses import dataclass

import numpy as np

from reachy_alive.brain.sensory_cortex.vision.vision_features import SeenFace

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


class VisionFacts:
    """What the robot sees, as facts. Read it as `shared_state.vision`.

    Each change is one event, written whole under the lock: a reader never
    sees a face that appeared without its position.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._face_seen_since: float | None = None
        self._last_face_lost_at: float | None = None
        self._main_face: SeenFace | None = None

    # Face presence. Written by FacePresenceDetector.

    def record_face_appeared(self, at: float, face: SeenFace) -> None:
        """Record that a face appeared at `at` (time.monotonic()), and where it is."""
        with self._lock:
            self._face_seen_since = at
            self._main_face = face

    def record_main_face(self, face: SeenFace) -> None:
        """Record where the face in view is now."""
        with self._lock:
            self._main_face = face

    def record_face_lost(self, at: float) -> None:
        """Record that the face left the view at `at` (time.monotonic())."""
        with self._lock:
            self._face_seen_since = None
            self._last_face_lost_at = at
            self._main_face = None

    def face_seen_since(self) -> float | None:
        """Return since when a face is in view (time.monotonic()), or None if none is."""
        with self._lock:
            return self._face_seen_since

    def last_face_lost_at(self) -> float | None:
        """Return when the last face left the view (time.monotonic()), or None if none did yet."""
        with self._lock:
            return self._last_face_lost_at

    def main_face(self) -> SeenFace | None:
        """Return the face in view, the nearest one if several, or None if none is."""
        with self._lock:
            return self._main_face


class InertialFacts:
    """What the robot feels through its inertial unit, as facts. Read it as `shared_state.inertial`."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._last_bump_at: float | None = None

    # Bumps. Written by BumpDetector.

    def record_bump(self, at: float) -> None:
        """Record a bump felt at `at` (time.monotonic())."""
        with self._lock:
            self._last_bump_at = at

    def last_bump_at(self) -> float | None:
        """Return when the last bump was felt (time.monotonic()), or None if none yet."""
        with self._lock:
            return self._last_bump_at


class TouchFacts:
    """What the robot feels through its antennas, as facts. Read it as `shared_state.touch`."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._antenna_pushed_since: dict[str, float | None] = {"right": None, "left": None}

    # Antenna pushes. Written by AntennaPushDetector.

    def record_antenna_pushed_since(self, side: str, since: float | None) -> None:
        """Record since when an antenna is pushed (time.monotonic()), or None once it isn't.

        Args:
            side: "right" or "left", the robot's own sides.
            since: When the push started, or None.
        """
        with self._lock:
            self._antenna_pushed_since[side] = since

    def antenna_pushed_since(self, side: str) -> float | None:
        """Return since when an antenna is pushed (time.monotonic()), or None if it isn't.

        Args:
            side: "right" or "left", the robot's own sides.
        """
        with self._lock:
            return self._antenna_pushed_since[side]


class HearingFacts:
    """What the robot hears, as facts. Read it as `shared_state.hearing`."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._last_sudden_noise_at: float | None = None

    # Sudden noises. Written by SuddenNoiseDetector.

    def record_sudden_noise(self, at: float) -> None:
        """Record a sudden noise that started at `at` (time.monotonic())."""
        with self._lock:
            self._last_sudden_noise_at = at

    def last_sudden_noise_at(self) -> float | None:
        """Return when the last sudden noise started (time.monotonic()), or None if none yet."""
        with self._lock:
            return self._last_sudden_noise_at


class SharedState:
    """Central, thread-safe blackboard of state shared across modules.

    It holds facts any module may read at any time, such as when the last
    move ended. It does not carry orders: a module that wants something done
    hands over a command instead (see reachy_alive.control.commands).

    Methods are grouped by fact. Each group names its one writer; every
    other module only reads. The facts of a sense live in their own object,
    such as `vision`.

    Attributes:
        lock: Guards all reads/writes to prevent race conditions.
        last_activity_at: Monotonic clock reading (time.monotonic()) of when
            the last move ended, whoever asked for the move. Starts at the
            app's launch.
        vision: What the robot sees.
        inertial: What the robot feels through its inertial unit.
        touch: What the robot feels through its antennas.
        hearing: What the robot hears.
    """

    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.last_activity_at: float = time.monotonic()
        self.vision = VisionFacts()
        self.inertial = InertialFacts()
        self.touch = TouchFacts()
        self.hearing = HearingFacts()
        self._move_playing = False
        self._last_move_ended_at: float | None = None
        self._commanded_pose: CommandedPose | None = None
        self._idle_move_interval_range_s = DEFAULT_IDLE_MOVE_INTERVAL_RANGE_S

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
        the robot up included, and when the last one ended.

        Args:
            playing: True when a move starts, False once it has ended.
        """
        with self.lock:
            self._move_playing = playing
            if not playing:
                self._last_move_ended_at = time.monotonic()

    def is_move_playing(self) -> bool:
        """Return whether RobotController is playing a move right now."""
        with self.lock:
            return self._move_playing

    def last_move_ended_at(self) -> float | None:
        """Return when the last move ended (time.monotonic()), or None if none did yet."""
        with self.lock:
            return self._last_move_ended_at

    def record_commanded_pose(self, pose: CommandedPose) -> None:
        """Record the pose RobotController just sent to the robot."""
        with self.lock:
            self._commanded_pose = pose

    def last_commanded_pose(self) -> CommandedPose | None:
        """Return the last pose RobotController sent, or None if none yet."""
        with self.lock:
            return self._commanded_pose

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

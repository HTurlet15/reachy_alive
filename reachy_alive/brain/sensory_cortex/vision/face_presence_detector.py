"""Face presence: whether someone is in view, from the faces the vision cortex sees."""

import logging

from reachy_alive.brain.sensory_cortex.vision.vision_frame import SeenFace, VisionFrame
from reachy_alive.shared_state import VisionFacts


class FacePresenceDetector:
    """Decides when a face appears and leaves, despite the face detector's flickers.

    A face appears once seen without a break for APPEAR_AFTER_S, and leaves once
    unseen for DISAPPEAR_AFTER_S. The facts keep when it was really first and
    last seen: the delays only make the detector sure.
    """

    # Long enough to ignore a face imagined in a single frame.
    APPEAR_AFTER_S = 0.4
    # Long enough to bridge the frames missed on a far face.
    DISAPPEAR_AFTER_S = 1.0
    # Farther faces are ignored. Provisional: to tune by eye on the robot.
    MAX_FACE_DISTANCE_M = 2.0

    def __init__(self, facts: VisionFacts) -> None:
        self._facts = facts
        self._in_view = False
        self._first_seen_at: float | None = None
        self._last_seen_at: float | None = None

    def update(self, frame: VisionFrame) -> None:
        """Follow the main face through one frame, and record what changed."""
        if frame.robot_moving_itself:
            return  # its own gesture blurs or turns the camera: no evidence either way
        face = self._main_face(frame)
        if face is None:
            self._follow_absence(frame.t)
        else:
            self._follow_face(frame.t, face)

    def _main_face(self, frame: VisionFrame) -> SeenFace | None:
        """Return the nearest face if it is close enough to count, or None."""
        if not frame.faces:
            return None
        nearest = frame.faces[0]
        return nearest if nearest.distance_m <= self.MAX_FACE_DISTANCE_M else None

    def _follow_face(self, t: float, face: SeenFace) -> None:
        """Note a face seen at `t`: it appears once seen long enough, then is followed."""
        if self._first_seen_at is None:
            self._first_seen_at = t
        self._last_seen_at = t
        if self._in_view:
            self._facts.record_main_face(face)
        elif self._seen_long_enough(t):
            self._in_view = True
            self._facts.record_face_appeared(self._first_seen_at, face)

    def _follow_absence(self, t: float) -> None:
        """Note that no face is seen at `t`.

        A face seen too briefly to count yet is forgotten: it must be seen anew,
        without a break. A face in view leaves once unseen long enough.
        """
        if not self._in_view:
            self._first_seen_at = None  # a break: the face must be seen anew
            return
        if self._unseen_long_enough(t):
            self._in_view = False
            self._first_seen_at = None
            self._facts.record_face_lost(self._last_seen_at)

    def _seen_long_enough(self, t: float) -> bool:
        return t - self._first_seen_at >= self.APPEAR_AFTER_S

    def _unseen_long_enough(self, t: float) -> bool:
        return t - self._last_seen_at >= self.DISAPPEAR_AFTER_S
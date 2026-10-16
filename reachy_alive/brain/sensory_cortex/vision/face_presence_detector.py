"""Face presence: whether someone is in view, from the faces the vision sense sees."""

import logging

from reachy_alive.brain.sensory_cortex.detector import Detector
from reachy_alive.brain.sensory_cortex.vision.vision_features import SeenFace, VisionFeatures
from reachy_alive.shared_state import VisionFacts

logger = logging.getLogger(__name__)


class FacePresenceDetector(Detector):
    """Decides when a face appears and leaves, despite the face detector's flickers.

    A face appears once seen without a break for APPEAR_AFTER_S, and leaves once
    unseen for DISAPPEAR_AFTER_S. The facts keep when it was really first and
    last seen: the delays only make the detector sure.
    """

    # Long enough to ignore a face imagined in a single image.
    APPEAR_AFTER_S = 0.4
    # Long enough to bridge the images where a far face is missed.
    DISAPPEAR_AFTER_S = 1.0
    # Farther faces are ignored. Provisional: to tune by eye on the robot.
    MAX_FACE_DISTANCE_M = 2.0

    def __init__(self, facts: VisionFacts) -> None:
        """Start with no face in view."""
        super().__init__(facts)
        self._in_view = False
        self._first_seen_at: float | None = None
        self._last_seen_at: float | None = None
        self._unseen_since: float | None = None

    def _detect(self, features: VisionFeatures) -> None:
        """Follow the nearest face through one image, and record what changed."""
        nearest = features.faces[0] if features.faces else None  # the sense sorts them
        if nearest is not None and nearest.distance_m <= self.MAX_FACE_DISTANCE_M:
            self._follow_face(features.perceived_at, nearest)
        else:
            self._follow_absence(features.perceived_at)

    def _while_robot_moves(self, features: VisionFeatures) -> None:
        """Count absence again from scratch once the move is over.

        The robot's own move blurs or turns the camera: no evidence either way.
        """
        self._unseen_since = None

    def _follow_face(self, t: float, face: SeenFace) -> None:
        """Note a face seen at `t`: it appears once seen long enough, then is followed."""
        if self._first_seen_at is None:
            self._first_seen_at = t
        self._last_seen_at = t
        self._unseen_since = None
        seen_long_enough = t - self._first_seen_at >= self.APPEAR_AFTER_S
        if self._in_view:
            self._facts.record_main_face(face)
        elif seen_long_enough:
            self._in_view = True
            self._facts.record_face_appeared(self._first_seen_at, face)
            logger.info("Face appeared, %.1f m away", face.distance_m)

    def _follow_absence(self, t: float) -> None:
        """Note that no face is seen at `t`.

        A face seen too briefly to count yet is forgotten: it must be seen anew,
        without a break. A face in view leaves once unseen long enough.
        """
        if not self._in_view:
            self._first_seen_at = None  # a break: the face must be seen anew
            return
        if self._unseen_since is None:
            self._unseen_since = t
        unseen_long_enough = t - self._unseen_since >= self.DISAPPEAR_AFTER_S
        if unseen_long_enough:
            self._in_view = False
            self._first_seen_at = None
            self._unseen_since = None
            self._facts.record_face_lost(self._last_seen_at)
            logger.info("Face lost")

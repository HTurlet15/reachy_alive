"""The face glance: the robot looks at a face that just appeared."""

import logging

import numpy as np

from reachy_alive.brain.basal_ganglia.proposal import Direction, Proposal
from reachy_alive.shared_state import SharedState

logger = logging.getLogger(__name__)


class FaceGlanceReflex:
    """Looks at a face once, when it appears.

    It reacts to each appearance once: a face that stays in view is not a
    new one. It proposes a direction only; the head turns there, and the body
    follows if the turn is large.
    """

    # How long the head takes to turn toward the face. Provisional: to check on the robot.
    TURN_DURATION_S = 0.5

    def __init__(self, shared_state: SharedState) -> None:
        """Keep where the facts are read.

        Args:
            shared_state: Read the faces in view, and the last pose sent.
        """
        self._shared_state = shared_state
        # When the face it last looked at appeared; None before the first one.
        self._looked_at_appearance_at: float | None = None

    def propose(self, now: float) -> Proposal | None:
        """Propose to look at the face in view if it just appeared; otherwise None.

        Args:
            now: This tick's time.monotonic() reading.
        """
        vision = self._shared_state.vision
        appeared_at = vision.face_seen_since()
        face = vision.main_face()
        if appeared_at is None or face is None or appeared_at == self._looked_at_appearance_at:
            return None

        self._looked_at_appearance_at = appeared_at
        # The face's angle is measured from where the camera, in the head, pointed.
        toward_face_rad = self._head_direction_rad() + face.yaw_rad
        logger.info("A face appeared: looking at %.0f°", np.degrees(toward_face_rad))
        return Proposal(
            source="face glance",
            direction=Direction(yaw_rad=toward_face_rad, duration_s=self.TURN_DURATION_S),
        )

    def _head_direction_rad(self) -> float:
        """Return where the head pointed in the last pose sent: 0 is the robot's front."""
        last_pose_sent = self._shared_state.last_commanded_pose()
        if last_pose_sent is None:
            return 0.0
        head = last_pose_sent.head
        return float(np.arctan2(head[1, 0], head[0, 0]))

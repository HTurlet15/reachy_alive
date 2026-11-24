"""The face glance: the robot looks at a face that just appeared, then lets go."""

import logging

import numpy as np

from reachy_alive.brain.basal_ganglia.proposal import Direction, Proposal
from reachy_alive.shared_state import SharedState

logger = logging.getLogger(__name__)


class FaceGlanceReflex:
    """Looks at a face when it appears, and lets go once it leaves or interest fades.

    It reacts to each appearance once: a face that stays in view is not a
    new one. Someone speaking keeps its interest: it lets go HOLD_S after
    the speech ends. It only proposes directions: the head turns toward the face, and
    the body follows if the turn is large. Letting go brings the head back
    over the body, which stays where it turned.
    """

    # How long the head takes to turn. Provisional: to check on the robot.
    TURN_DURATION_S = 1.0
    # How long it keeps looking after the last sign of interest: the face
    # appearing, or speech. Provisional: to check on the robot.
    HOLD_S = 4.0

    def __init__(self, shared_state: SharedState) -> None:
        """Keep where the facts are read.

        Args:
            shared_state: Read the faces in view, speech, and the last pose sent.
        """
        self._shared_state = shared_state
        # When the face it last looked at appeared; None before the first one.
        self._looked_at_appearance_at: float | None = None
        # Whether it is still looking at that face.
        self._looking = False

    def propose(self, now: float) -> Proposal | None:
        """Propose to look at a face that just appeared, or to let go of it; otherwise None.

        Args:
            now: This tick's time.monotonic() reading.
        """
        appeared_at = self._shared_state.vision.face_seen_since()

        # 1. It is looking at a face: it lets go once the face left, or interest faded.
        if self._looking:
            face_left = appeared_at != self._looked_at_appearance_at
            interest_faded = now - self._last_sign_of_interest_at(now) >= self.HOLD_S
            if face_left or interest_faded:
                return self._let_go()
            return None

        # 2. A face it has not looked at yet: it looks.
        if appeared_at is not None and appeared_at != self._looked_at_appearance_at:
            return self._look_at_face(appeared_at)

        # 3. Nothing new.
        return None

    def _last_sign_of_interest_at(self, now: float) -> float:
        """Return when interest last showed: now while someone speaks, else the latest sign.

        The signs: the face appearing, and the last speech ending. Speech counts
        whoever speaks: the robot can't tell whether it comes from the face.
        """
        hearing = self._shared_state.hearing
        if hearing.speaking_since() is not None:
            return now
        last_speech_ended_at = hearing.last_speech_ended_at()
        if last_speech_ended_at is None:
            return self._looked_at_appearance_at
        return max(self._looked_at_appearance_at, last_speech_ended_at)

    def _look_at_face(self, appeared_at: float) -> Proposal | None:
        """Start looking at the face in view, and propose its direction."""
        face = self._shared_state.vision.main_face()
        if face is None:
            return None
        self._looked_at_appearance_at = appeared_at
        self._looking = True
        # The face's angle is measured from where the camera, in the head, pointed.
        toward_face_rad = self._head_direction_rad() + face.yaw_rad
        logger.info("A face appeared: looking at %.0f°", np.degrees(toward_face_rad))
        return self._turn_to(toward_face_rad)

    def _let_go(self) -> Proposal:
        """Stop looking, and propose to bring the head back over the body."""
        self._looking = False
        logger.info("Letting go of the face")
        return self._turn_to(self._body_direction_rad())

    def _turn_to(self, yaw_rad: float) -> Proposal:
        """Return a proposal to turn the head toward yaw_rad."""
        return Proposal(
            source="face glance",
            direction=Direction(yaw_rad=yaw_rad, duration_s=self.TURN_DURATION_S),
        )

    def _head_direction_rad(self) -> float:
        """Return where the head pointed in the last pose sent: 0 is the robot's front."""
        last_pose_sent = self._shared_state.last_commanded_pose()
        if last_pose_sent is None:
            return 0.0
        head = last_pose_sent.head
        return float(np.arctan2(head[1, 0], head[0, 0]))

    def _body_direction_rad(self) -> float:
        """Return where the body faced in the last pose sent: 0 is the robot's front."""
        last_pose_sent = self._shared_state.last_commanded_pose()
        if last_pose_sent is None or last_pose_sent.body_yaw is None:
            return 0.0
        return last_pose_sent.body_yaw

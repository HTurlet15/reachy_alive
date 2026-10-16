"""The vision sense: the faces the camera sees, a few times a second."""

import numpy as np
from reachy_mini import ReachyMini
from reachy_mini.vision.face_detector import Face, FaceDetector

from reachy_alive.brain.sensory_cortex.sense import Sense
from reachy_alive.brain.sensory_cortex.vision.vision_features import SeenFace, VisionFeatures
from reachy_alive.shared_state import SharedState


class VisionSense(Sense):
    """Looks through the camera and describes each image by its VisionFeatures."""

    PERIOD_S = 0.2
    # Wide enough to find a face up to about 2.5 m; each doubling costs about
    # twice the time to find faces.
    ANALYSED_WIDTH_PX = 320
    # Width of an average face, as the face detector boxes it: wider than the face
    # itself, ears and hair included. Measured with a tape, 0.5 to 2.5 m. Faces vary
    # by about 20%, and so does the distance estimated from it.
    AVERAGE_FACE_WIDTH_M = 0.195

    def __init__(
        self,
        reachy_mini: ReachyMini,
        shared_state: SharedState,
        face_finder: FaceDetector | None = None,
    ) -> None:
        """Set up the face finder.

        Args:
            reachy_mini: Connected robot instance, only looked through.
            shared_state: Where the sense learns whether the robot is moving itself.
            face_finder: Finds the faces in one image: the SDK's YuNet model by
                default, a stand-in in tests. Not one of our detectors: it has
                no memory, no threshold of ours, and records no fact.
        """
        super().__init__(reachy_mini, shared_state)
        self._face_finder = face_finder or FaceDetector()

    def is_available(self) -> bool:
        """Return whether the robot has a camera to look through."""
        return self._reachy_mini.media.camera is not None

    def _perceive(self, t: float, robot_moving_itself: bool) -> VisionFeatures | None:
        """Describe the faces in the latest image, or return None if the camera isn't ready yet."""
        image = self._reachy_mini.media.get_frame()
        camera_matrix = self._reachy_mini.media.camera.K
        if image is None or camera_matrix is None:
            return None
        return VisionFeatures(
            t=t,
            faces=self._find_faces(image, camera_matrix),
            robot_moving_itself=robot_moving_itself,
        )

    def _find_faces(self, image: np.ndarray, camera_matrix: np.ndarray) -> tuple[SeenFace, ...]:
        """Find the faces in a shrunk copy of the image, nearest first."""
        full_width_px = image.shape[1]
        # Keeps one pixel in `step` each way: fast, and enough for faces.
        step = max(1, full_width_px // self.ANALYSED_WIDTH_PX)
        small_image = image[::step, ::step]
        height_px, width_px = small_image.shape[:2]
        focal_px = float(camera_matrix[0, 0]) * width_px / full_width_px

        faces = [
            VisionSense.seen_face(face, width_px, height_px, focal_px)
            for face in self._face_finder.detect(small_image)
        ]
        return tuple(sorted(faces, key=lambda face: face.distance_m))

    @staticmethod
    def seen_face(face: Face, image_width_px: int, image_height_px: int, focal_px: float) -> SeenFace:
        """Describe a face found by the face finder: where it is, and how far.

        Args:
            face: A face found by the face finder, in pixels.
            image_width_px: Width of the image the face was found in.
            image_height_px: Height of that image.
            focal_px: The camera's focal length, in pixels of that image.
        """
        left_px, top_px, width_px, height_px = face.bbox
        center_x_px = left_px + width_px / 2
        center_y_px = top_px + height_px / 2
        return SeenFace(
            # From pixels to -1 at one edge, 0 at the center, 1 at the other edge.
            x=2 * center_x_px / image_width_px - 1,
            y=2 * center_y_px / image_height_px - 1,
            # A pinhole camera: an object's size in the image shrinks with its distance.
            distance_m=focal_px * VisionSense.AVERAGE_FACE_WIDTH_M / width_px,
        )
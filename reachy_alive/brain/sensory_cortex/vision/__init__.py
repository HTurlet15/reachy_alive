"""Vision: what the robot sees through its camera.

The sense (vision_sense.py) describes each image by its VisionFeatures
(vision_features.py): the faces in view, nearest first. Every `*_detector.py`
file in this folder is a detector: it reads the features and records facts in
`shared_state.vision`. FacePresenceDetector (face_presence_detector.py)
decides when someone appears and leaves.
"""

"""Inertial: what the robot feels through its inertial unit.

The sense (inertial_sense.py) describes each reading by its InertialFeatures
(inertial_features.py): the acceleration, and whether the robot was moving
itself. Every `*_detector.py` file in this folder is a detector: it reads the
features and records facts in `shared_state.inertial`. BumpDetector (bump_detector.py)
spots a knock on the robot or on its table.
"""

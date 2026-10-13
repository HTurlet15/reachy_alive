"""Touch: what the robot feels through its antennas.

The sense (touch_sense.py) describes each reading as a TouchFrame
(touch_frame.py): where each antenna was sent, and where it is. Every
`*_detector.py` file in this folder is a detector: it reads the frames and
records facts in `shared_state.touch`. AntennaPushDetector
(antenna_push_detector.py) spots someone pushing an antenna.
"""
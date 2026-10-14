"""Hearing: what the robot hears through its microphones.

The sense (hearing_sense.py) describes each 20 ms stretch of sound by its
HearingFeatures (hearing_features.py): how loud it is. Every `*_detector.py`
file in this folder is a detector: it reads the features and records facts in
`shared_state.hearing`. SuddenNoiseDetector (sudden_noise_detector.py) spots
a sudden noise, like a clap or a door slamming.
"""
# Touch

What the robot feels through its antennas: where they are, against where
they were sent. For the steps every detector follows, see
[`../README.md`](../README.md).

## What it gives

One `TouchFeatures` 50 times a second, each value for both antennas, in
`ANTENNA_SIDES` order (right, then left):

- `targets_rad`: where each antenna was last sent, in radians.
- `measured_rad`: where each antenna is, measured.
- `antennas_enabled`: whether each antenna is felt. The page switches them
  off one by one, such as a faulty one.
- Like every sense: `perceived_at` and `robot_moving_itself`.

Details in [`touch_features.py`](touch_features.py).

## Watch out for

- **The antennas never stop.** They sway with the breathing, and the motor
  runs behind its target: about 80 ms on the left, 110 ms on the right.
  Compare the measure to the targets sent a moment ago, not to the latest
  one.
- **Antennas differ from robot to robot.** Some sway in jerks, as far as a
  push. The page can switch one off: forget an antenna while
  `antennas_enabled` says it isn't felt.
- **Simulation swaps the order**: the left antenna comes first there.

## Detectors

| Detector | Records | How |
|---|---|---|
| `AntennaPushDetector` | an antenna pushed, and since when | The measure stands outside where the motor's lag allows it to be |

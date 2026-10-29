# Inertial unit

What the robot feels through the inertial unit in its head. For the steps
every detector follows, see [`../README.md`](../README.md).

## What it gives

One `InertialFeatures` 50 times a second:

- `accelerometer`: the (x, y, z) acceleration, in m/s², gravity included.
- Like every sense: `perceived_at` and `robot_moving_itself`.

Details in [`inertial_features.py`](inertial_features.py).

## Watch out for

- **The unit is in the head.** Gravity moves from one axis to another as
  the head tilts. The acceleration's norm doesn't: at rest it stays near
  9.8 m/s², whatever the pose.
- **A bump is short.** A knock on the head or the table moves the norm by
  5 to 9 m/s² for one or two readings, then the head rings for a moment.
  Breathing moves it by less than 1.
- **No data in simulation**, nor on the Lite: the sense then gives nothing.

## Detectors

| Detector | Records | How |
|---|---|---|
| `BumpDetector` | a bump | The norm strays from gravity; the readings right after are ignored |

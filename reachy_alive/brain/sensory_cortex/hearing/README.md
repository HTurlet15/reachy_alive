# Hearing

What the robot hears through its microphones. For the steps every
detector follows, see [`../README.md`](../README.md).

## What it gives

One `HearingFeatures` every 20 ms, a frame of sound:

- `level_dbfs`: how loud the frame is, in dBFS. 0 is the loudest the
  microphones report; every -6 dB halves the sound.
- `time_listened_s`: how long the sense has listened, at the end of the
  frame: the sound's own clock.
- Like every sense: `perceived_at` and `robot_moving_itself`.

Details in [`hearing_features.py`](hearing_features.py).

## Watch out for

- **Absolute levels mean little.** The microphones adjust their gain on
  their own: it rises in a quiet room and drops when someone talks. Compare
  a level to the recent background (`Background`, in `detector.py`), not to
  a fixed number.
- **Follow the sound with `time_listened_s`.** Sound arrives late or
  bunched up: `perceived_at` says when a frame was read, `time_listened_s`
  where it sits in the sound.
- **A loud sound doesn't say what it was.** A clap, the first word after a
  silence and a TV changing scene all jump 30 dB or more above the
  background.

## Detectors

| Detector | Records | How |
|---|---|---|
| `SuddenNoiseDetector` | a sudden noise | A jump above the background; a loud sound right after another is expected |

# Vision

What the robot sees through its camera: for now, faces. For the steps every
detector follows, see [`../README.md`](../README.md).

## What it gives

One `VisionFeatures` 5 times a second:

- `faces`: every face in view, nearest first. Each `SeenFace` has:
  - `x`: from -1 at the left edge of the view to 1 at the right, as the
    robot sees it;
  - `y`: from -1 at the top edge to 1 at the bottom;
  - `distance_m`: how far it is from the camera, estimated from its size.
- Like every sense: `perceived_at` and `robot_moving_itself`.

No image: the sense finds the faces, detectors read them. Details in
[`vision_features.py`](vision_features.py).

## Watch out for

- **Faces flicker.** The face finder sometimes imagines a face in a single
  image, and misses a far face for a few. Wait before deciding a face came
  or went.
- **Faces are found up to about 2 m**, less reliably at 2.5 m, and the
  distance is right to within about 20 %: faces differ.
- **Left and right are the robot's**, not yours when you face it.

## Detectors

| Detector | Records | How |
|---|---|---|
| `FacePresenceDetector` | a face in view, since when, and where; when it left | A face seen without a break for a moment appears; unseen for a while, it leaves |

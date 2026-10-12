"""Diagnosis: check the face features on the real camera (distance, range, side).

Throwaway code, never merged. The app must NOT be running. Usage:
    uv run python spike/vision/faces_measure.py faces_measure.csv

The robot wakes up, then stays still. Follow the instructions printed on screen,
with a tape measure: stand at each distance, facing the robot, your face at the
height of its head. It prints what the robot sees twice a second and writes
faces_measure.csv. No image is kept, only numbers. The robot goes back to sleep
at the end, even after Ctrl+C.
"""

import csv
import sys
import time

from reachy_mini import ReachyMini
from reachy_mini.vision.face_detector import FaceDetector

from reachy_alive.brain.sensory_cortex.vision.vision_cortex import seen_face

ANALYSED_WIDTH_PX = int(sys.argv[2]) if len(sys.argv) > 2 else 320
PRINT_PERIOD_S = 0.5
DURATION_S = 90
CSV_HEADER = ["clock_s", "faces", "x", "y", "distance_m", "box_width_px", "detect_ms"]

# What to do, and when: printed when the clock reaches each second.
INSTRUCTIONS = {
    0: "Face the robot, 0.5 m away, in the middle of its view",
    10: "1 m away",
    20: "1.5 m away",
    30: "2 m away",
    40: "2.5 m away",
    50: "Stay at 2.5 m, do not move",
    60: "Back to 1 m, then step slowly to YOUR right (the robot's left)",
    70: "Now slowly to YOUR left (the robot's right)",
    80: "Leave the robot's view",
}


def main(path: str) -> None:
    detector = FaceDetector()
    with ReachyMini() as mini:
        mini.enable_motors()  # asleep, the motors may have no torque
        mini.wake_up()  # head up: the camera faces the room
        try:
            rows = measure(mini, detector)
        finally:
            mini.goto_sleep()
    save(path, rows)


def measure(mini: ReachyMini, detector: FaceDetector) -> list[list]:
    """Analyse images for DURATION_S, as the cortex will, and return one row per image."""
    rows = []
    t0 = time.monotonic()
    last_second = -1
    next_print_s = 0.0
    while (elapsed_s := time.monotonic() - t0) < DURATION_S:
        if int(elapsed_s) != last_second:
            last_second = int(elapsed_s)
            if last_second in INSTRUCTIONS:
                print(f"\n{last_second:2d} s  >>> {INSTRUCTIONS[last_second]}")

        frame = mini.media.get_frame()
        if frame is None:
            continue
        full_width_px = frame.shape[1]
        # One pixel in `step` each way, as the cortex will analyse it.
        step = max(1, full_width_px // ANALYSED_WIDTH_PX)
        image = frame[::step, ::step]
        height_px, width_px = image.shape[:2]
        focal_px = float(mini.media.camera.K[0, 0]) * width_px / full_width_px

        detect_started = time.monotonic()
        faces = detector.detect(image)
        detect_ms = 1000 * (time.monotonic() - detect_started)

        seen = sorted(
            (seen_face(face, width_px, height_px, focal_px) for face in faces),
            key=lambda face: face.distance_m,
        )
        nearest = seen[0] if seen else None
        # The nearest face has the widest box.
        box_width_px = max((face.bbox[2] for face in faces), default=0.0)
        rows.append([
            f"{elapsed_s:.2f}",
            len(seen),
            "" if nearest is None else f"{nearest.x:.2f}",
            "" if nearest is None else f"{nearest.y:.2f}",
            "" if nearest is None else f"{nearest.distance_m:.2f}",
            f"{box_width_px:.1f}",
            f"{detect_ms:.1f}",
        ])

        if elapsed_s >= next_print_s:
            next_print_s += PRINT_PERIOD_S
            if nearest is None:
                print(f"  {elapsed_s:5.1f} s  no face  ({detect_ms:.0f} ms)")
            else:
                print(
                    f"  {elapsed_s:5.1f} s  {len(seen)} face(s)  nearest: "
                    f"x={nearest.x:+.2f} y={nearest.y:+.2f} "
                    f"distance={nearest.distance_m:.2f} m  box={box_width_px:.0f} px  "
                    f"({detect_ms:.0f} ms, image {width_px}x{height_px}, focal {focal_px:.0f} px)"
                )
    return rows


def save(path: str, rows: list[list]) -> None:
    with open(path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(CSV_HEADER)
        writer.writerows(rows)
    print(f"\nSaved {path}: {len(rows)} images analysed in {DURATION_S} s")


if __name__ == "__main__":
    main(sys.argv[1])
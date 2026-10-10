"""Spike: look through the camera, measure motion and faces, and what it costs.

Throwaway code, never merged. The app must NOT be running: this script moves
the head itself (asleep, the camera sees the inside of the shell). It only
needs numpy and reachy_mini, so it also runs on the robot. Usage:
    uv run python spike/vision/vision_record.py spike/vision/still 40
    uv run python spike/vision/vision_record.py spike/vision/breathe 20 --breathe
"""

import csv
import sys
import time

import numpy as np
from reachy_mini import ReachyMini
from reachy_mini.utils import create_head_pose
from reachy_mini.vision.face_detector import FaceDetector

TARGET_WIDTH = 320  # frames are shrunk to about this width, like the daemon does
MOTION_THRESHOLD = 15  # gray levels (0-255) for a pixel to count as changed
SNAPSHOT_PERIOD_S = 5.0
HEAD_PERIOD_S = 1 / 50  # how often the head target is sent while breathing


def downscale(frame: np.ndarray) -> np.ndarray:
    """Keep one pixel out of `step` in each direction: cheap, no library needed."""
    step = max(1, frame.shape[1] // TARGET_WIDTH)
    return np.ascontiguousarray(frame[::step, ::step])


def main(prefix: str, duration_s: float, breathe: bool) -> None:
    detector = FaceDetector()  # downloads the model on first use
    rows, snapshots = [], []
    previous_raw = previous_gray = None
    full_shape = small_shape = None
    with ReachyMini() as mini:
        mini.enable_motors()
        mini.goto_target(head=create_head_pose(), duration=2.0)
        cpu_start = time.process_time()
        t0 = time.monotonic()
        next_snapshot_s = 0.0
        next_head_s = 0.0
        last_second = -1
        try:
            while (t := time.monotonic() - t0) < duration_s:
                if int(t) != last_second:  # a clock to time your actions
                    last_second = int(t)
                    print(f"{last_second} s")
                if breathe and t >= next_head_s:  # same motion as the app's breathing
                    next_head_s += HEAD_PERIOD_S
                    z_mm = 4.0 * np.sin(2 * np.pi * 0.25 * t)
                    mini.set_target(head=create_head_pose(z=z_mm, mm=True))

                frame = mini.media.get_frame()
                if frame is None or (previous_raw is not None and np.array_equal(frame, previous_raw)):
                    time.sleep(0.002)  # no new frame yet
                    continue
                previous_raw = frame
                small = downscale(frame)
                full_shape, small_shape = frame.shape, small.shape

                gray = small.mean(axis=2)
                motion = 0.0
                if previous_gray is not None:
                    motion = float(np.mean(np.abs(gray - previous_gray) > MOTION_THRESHOLD))
                previous_gray = gray

                start = time.perf_counter()
                faces = detector.detect(small)
                detect_ms = (time.perf_counter() - start) * 1000
                largest_px = max((f.bbox[2] - f.bbox[0] for f in faces), default=0.0)

                rows.append([f"{t:.3f}", f"{motion:.4f}", len(faces), f"{largest_px:.1f}", f"{detect_ms:.1f}"])
                if t >= next_snapshot_s:
                    next_snapshot_s += SNAPSHOT_PERIOD_S
                    snapshots.append(small)
        finally:
            cpu_s = time.process_time() - cpu_start
            wall_s = time.monotonic() - t0
            mini.goto_sleep()
            mini.disable_motors()

    with open(f"{prefix}.csv", "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["t_s", "motion_fraction", "n_faces", "largest_face_px", "detect_ms"])
        writer.writerows(rows)
    if snapshots:
        np.savez_compressed(f"{prefix}_snapshots.npz", *snapshots)

    detect = np.array([float(r[4]) for r in rows]) if rows else np.zeros(1)
    print(f"frame {full_shape}, analysed at {small_shape}")
    print(f"{len(rows) / wall_s:.1f} new frames analysed per second")
    print(f"face detection: median {np.median(detect):.1f} ms, 95th percentile {np.percentile(detect, 95):.1f} ms")
    print(f"this script used {100 * cpu_s / wall_s:.0f}% of one CPU core")


if __name__ == "__main__":
    main(sys.argv[1], float(sys.argv[2]), breathe="--breathe" in sys.argv)

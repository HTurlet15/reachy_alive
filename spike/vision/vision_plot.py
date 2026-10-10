"""Spike: plot a recording made by vision_record.py, and what the camera saw.

Throwaway code, never merged. Usage:
    MPLBACKEND=Agg uv run --with matplotlib python spike/vision/vision_plot.py spike/vision/still
"""

import csv
import sys

import matplotlib.pyplot as plt
import numpy as np


def main(prefix: str) -> None:
    with open(f"{prefix}.csv") as f:
        rows = list(csv.DictReader(f))
    t = np.array([float(r["t_s"]) for r in rows])
    motion = np.array([float(r["motion_fraction"]) for r in rows]) * 100
    n_faces = np.array([int(r["n_faces"]) for r in rows])
    largest = np.array([float(r["largest_face_px"]) for r in rows])
    detect_ms = np.array([float(r["detect_ms"]) for r in rows])

    fig, (ax_m, ax_f, ax_c) = plt.subplots(3, 1, sharex=True, figsize=(12, 9))
    ax_m.plot(t, motion)
    ax_m.set_ylabel("pixels changed (%)")
    ax_f.plot(t, n_faces, label="faces found")
    ax_f2 = ax_f.twinx()
    ax_f2.plot(t, largest, "C1", alpha=0.6, label="largest face width")
    ax_f.set_ylabel("faces found")
    ax_f2.set_ylabel("largest face width (px)", color="C1")
    ax_c.plot(t, detect_ms)
    ax_c.set_ylabel("face detection (ms)")
    ax_c.set_xlabel("time (s)")
    for ax in (ax_m, ax_f, ax_c):
        ax.grid(True)
    fig.suptitle(prefix)
    fig.savefig(f"{prefix}.png", dpi=120)
    print(f"Saved {prefix}.png")

    snapshots = np.load(f"{prefix}_snapshots.npz")
    frames = [snapshots[k] for k in snapshots.files]
    fig, axes = plt.subplots(1, len(frames), figsize=(3 * len(frames), 3), squeeze=False)
    for i, (ax, frame) in enumerate(zip(axes[0], frames)):
        ax.imshow(frame[:, :, ::-1])  # BGR to RGB
        ax.set_title(f"{i * 5} s")
        ax.axis("off")
    fig.savefig(f"{prefix}_snapshots.png", dpi=100, bbox_inches="tight")
    print(f"Saved {prefix}_snapshots.png")


if __name__ == "__main__":
    main(sys.argv[1])

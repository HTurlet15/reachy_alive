"""Spike: plot an IMU recording made by imu_record.py.

Throwaway code, never merged. matplotlib isn't a project dependency, so
uv brings it in just for this run:
    uv run --with matplotlib python spike/imu_plot.py rest.csv
"""

import csv
import sys

import matplotlib.pyplot as plt
import numpy as np


def main(path: str) -> None:
    with open(path) as f:
        rows = list(csv.DictReader(f))
    t = np.array([float(r["t_s"]) for r in rows])
    accel = np.array([[float(r[k]) for k in ("ax", "ay", "az")] for r in rows])
    gyro = np.array([[float(r[k]) for k in ("gx", "gy", "gz")] for r in rows])

    fig, (ax_a, ax_g) = plt.subplots(2, 1, sharex=True, figsize=(12, 7))
    for i, axis in enumerate("xyz"):
        ax_a.plot(t, accel[:, i], label=axis, alpha=0.6)
        ax_g.plot(t, gyro[:, i], label=axis, alpha=0.6)
    ax_a.plot(t, np.linalg.norm(accel, axis=1), "k", label="norm")
    ax_g.plot(t, np.linalg.norm(gyro, axis=1), "k", label="norm")
    ax_a.set_ylabel("accelerometer (m/s²)")
    ax_g.set_ylabel("gyroscope (rad/s)")
    ax_g.set_xlabel("time (s)")
    for ax in (ax_a, ax_g):
        ax.grid(True)
        ax.legend(loc="upper right")
    fig.suptitle(path)
    out = path.replace(".csv", ".png")
    fig.savefig(out, dpi=120)
    print(f"Saved {out}")


if __name__ == "__main__":
    main(sys.argv[1])

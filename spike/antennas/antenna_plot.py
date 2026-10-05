"""Spike: plot an antenna recording made by antenna_record.py.

Throwaway code, never merged. Usage:
    uv run --with matplotlib python spike/antenna_plot.py hold.csv
"""

import csv
import sys

import matplotlib.pyplot as plt
import numpy as np


def main(path: str) -> None:
    with open(path) as f:
        rows = list(csv.DictReader(f))
    t = np.array([float(r["t_s"]) for r in rows])
    target = np.rad2deg([[float(r["target_0"]), float(r["target_1"])] for r in rows])
    present = np.rad2deg([[float(r["present_0"]), float(r["present_1"])] for r in rows])
    error = present - target

    fig, axes = plt.subplots(3, 1, sharex=True, figsize=(12, 9))
    for i in range(2):
        axes[i].plot(t, target[:, i], "k--", label="target")
        axes[i].plot(t, present[:, i], label="present (measured)")
        axes[i].set_ylabel(f"antenna {i} (deg)")
    axes[2].plot(t, error[:, 0], label="antenna 0")
    axes[2].plot(t, error[:, 1], label="antenna 1")
    axes[2].set_ylabel("present - target (deg)")
    axes[2].set_xlabel("time (s)")
    for ax in axes:
        ax.grid(True)
        ax.legend(loc="upper right")
    fig.suptitle(path)
    out = path.replace(".csv", ".png")
    fig.savefig(out, dpi=120)
    print(f"Saved {out}")
    print(f"error at rest (first 5 s): max {np.abs(error[t < 5]).max():.2f} deg")


if __name__ == "__main__":
    main(sys.argv[1])

"""Spike: hold the antennas still, or sway them, and record where they really are.

Throwaway code, never merged. The app must NOT be running: this script drives
the robot itself. Usage:
    uv run python spike/antenna_record.py hold.csv 40
    uv run python spike/antenna_record.py sway.csv 40 --sway
"""

import csv
import sys
import time

import numpy as np
from reachy_mini import ReachyMini
from reachy_mini.utils import create_head_pose

from reachy_alive.moves.base import NEUTRAL_ANTENNAS_RAD

PERIOD_S = 1 / 50
SWAY_AMPLITUDE_RAD = np.deg2rad(15.0)  # same sway as breathing
SWAY_FREQUENCY_HZ = 0.25


def main(path: str, duration_s: float, sway: bool) -> None:
    neutral_head = create_head_pose()
    neutral_antennas = np.array(NEUTRAL_ANTENNAS_RAD)
    with ReachyMini(media_backend="no_media") as mini, open(path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["t_s", "target_0", "target_1", "present_0", "present_1"])
        mini.enable_motors()
        # Ease into neutral before streaming targets (see CLAUDE.md).
        mini.goto_target(head=neutral_head, antennas=neutral_antennas, duration=1.0)
        try:
            t0 = time.monotonic()
            last_second = -1
            while (t := time.monotonic() - t0) < duration_s:
                if int(t) != last_second:  # a clock to time your actions
                    last_second = int(t)
                    print(f"{last_second} s")
                s = SWAY_AMPLITUDE_RAD * np.sin(2 * np.pi * SWAY_FREQUENCY_HZ * t) if sway else 0.0
                target = neutral_antennas + np.array([s, -s])
                mini.set_target(head=neutral_head, antennas=target)
                present = mini.get_present_antenna_joint_positions()
                writer.writerow([f"{t:.3f}", *target, *present])
                time.sleep(PERIOD_S)
        finally:
            mini.goto_sleep()
            mini.disable_motors()
    print(f"Saved {path}")


if __name__ == "__main__":
    main(sys.argv[1], float(sys.argv[2]), sway="--sway" in sys.argv)

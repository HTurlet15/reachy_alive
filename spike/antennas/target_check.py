"""Spike: read the antennas' measured positions and targets from the daemon.

Throwaway code, never merged. Only reads: run it WHILE the app runs, so the
targets come from the app (breathing, moves). Writes the same columns as
antenna_record.py, so antenna_plot.py can plot it. Usage:
    uv run python spike/antennas/target_check.py spike/antennas/target_check.csv 30
"""

import csv
import json
import sys
import time
import urllib.request

URL = (
    "http://reachy-mini.local:8000/api/state/full"
    "?with_control_mode=false&with_head_pose=false&with_body_yaw=false"
    "&with_antenna_positions=true&with_target_antenna_positions=true"
)
PERIOD_S = 1 / 50


def main(path: str, duration_s: float) -> None:
    rows = []
    t0 = time.monotonic()
    last_second = -1
    while (t := time.monotonic() - t0) < duration_s:
        if int(t) != last_second:  # a clock to time your actions
            last_second = int(t)
            print(f"{last_second} s")
        with urllib.request.urlopen(URL, timeout=0.5) as response:
            state = json.load(response)
        present = state["antennas_position"]
        target = state["target_antennas_position"]
        rows.append([f"{t:.3f}", *target, *present])
        time.sleep(PERIOD_S)

    with open(path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["t_s", "target_0", "target_1", "present_0", "present_1"])
        writer.writerows(rows)
    print(f"Saved {path}: {len(rows) / duration_s:.1f} readings per second")


if __name__ == "__main__":
    main(sys.argv[1], float(sys.argv[2]))

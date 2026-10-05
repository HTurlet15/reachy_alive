"""Spike: record the IMU for a while, to see what it actually gives.

Throwaway code, never merged. Usage:
    uv run python spike/imu_record.py rest.csv 40
"""

import csv
import sys
import time

from reachy_mini import ReachyMini

PERIOD_S = 1 / 50  # the daemon refreshes the IMU at 50 Hz
COLUMNS = ["t_s", "ax", "ay", "az", "gx", "gy", "gz", "qw", "qx", "qy", "qz", "temp_c"]


def main(path: str, duration_s: float) -> None:
    missing_reported = False
    last_second = -1
    with ReachyMini(media_backend="no_media") as mini, open(path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(COLUMNS)
        t0 = time.monotonic()
        while (t := time.monotonic() - t0) < duration_s:
            if int(t) != last_second:  # a clock to time your actions
                last_second = int(t)
                print(f"{last_second} s")
            imu = mini.imu
            if imu is None:
                if not missing_reported:
                    print("No IMU data (Lite, simulation, or nothing received yet)")
                    missing_reported = True
            else:
                writer.writerow(
                    [f"{t:.3f}", *imu["accelerometer"], *imu["gyroscope"],
                     *imu["quaternion"], imu["temperature"]]
                )
            time.sleep(PERIOD_S)
    print(f"Saved {path}")


if __name__ == "__main__":
    main(sys.argv[1], float(sys.argv[2]))

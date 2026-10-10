"""Diagnosis: record loudness levels, to choose the sudden-noise thresholds from data.

Throwaway code, never merged. The app must NOT be running. Usage:
    uv run --with matplotlib python spike/hearing/levels_record.py levels_room.csv

Follow the instructions printed on screen. It writes levels_room.csv, one row
per 20 ms stretch, timed by the on-screen clock and by the sound heard. No sound
is kept, only how loud it was. It also writes levels_room.png.
"""

import csv
import json
import math
import sys
import time
import urllib.request

import matplotlib

matplotlib.use("Agg")  # draw to a file only: no window, nothing to wait for
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from reachy_mini import ReachyMini  # noqa: E402

from reachy_alive.brain.sensory_cortex.hearing import SuddenNoiseDetector, loudness_dbfs  # noqa: E402

STRETCH_SAMPLES = 320  # 20 ms at 16 kHz
DURATION_S = 100
GAIN_URL = "http://reachy-mini.local:8000/api/audio/config/parameter/PP_AGCGAIN"
GAIN_PERIOD_S = 0.5

# What to do, and when: printed when the clock reaches each second.
INSTRUCTIONS = {
    0: "Hands off the keyboard. Silence for one minute: the gain rises",
    59: "get ready to talk, 1 m from the robot",
    60: ">>> NOW: talk normally, short sentences with pauses",
    70: "Silence",
    74: "get ready to clap, 1 m from the robot",
    75: ">>> NOW: clap once",
    78: ">>> NOW: clap once",
    81: ">>> NOW: clap once",
    84: "get ready: mouse, on the robot's table",
    85: ">>> NOW: put the mouse down",
    88: ">>> NOW: put the mouse down",
    90: "get ready to talk LOUDLY, 1 m from the robot",
    91: ">>> NOW: talk loudly, short sentences",
    96: "Silence until the end",
}


def read_agc_gain() -> float | None:
    """Return the microphones' automatic gain (a factor, not dB), or None if unavailable."""
    try:
        with urllib.request.urlopen(GAIN_URL, timeout=0.2) as response:
            return float(json.load(response)["values"][0])
    except (OSError, KeyError, ValueError):
        return None


def record(path: str) -> None:
    detector = SuddenNoiseDetector()
    rows = []
    samples_not_judged_yet = []
    sound_heard_s = 0.0
    with ReachyMini() as mini:
        mini.media.start_recording()
        t0 = time.monotonic()
        last_second = -1
        agc_gain = read_agc_gain()
        next_gain_read_s = GAIN_PERIOD_S
        try:
            while (elapsed_s := time.monotonic() - t0) < DURATION_S:
                if int(elapsed_s) != last_second:  # a clock to time your actions
                    last_second = int(elapsed_s)
                    print(f"{last_second:2d} s  {INSTRUCTIONS.get(last_second, '')}")
                if elapsed_s >= next_gain_read_s:
                    next_gain_read_s += GAIN_PERIOD_S
                    agc_gain = read_agc_gain() or agc_gain
                chunk = mini.media.get_audio_sample()
                if chunk is None:
                    continue
                samples_not_judged_yet.extend(chunk.mean(axis=1))
                while len(samples_not_judged_yet) >= STRETCH_SAMPLES:
                    stretch = samples_not_judged_yet[:STRETCH_SAMPLES]
                    del samples_not_judged_yet[:STRETCH_SAMPLES]
                    sound_heard_s += 0.02
                    level_dbfs = loudness_dbfs(np.asarray(stretch))
                    # Read before update(): the background the level is compared to.
                    background_dbfs = detector._background_dbfs
                    noise_starts = detector.update(sound_heard_s, level_dbfs)
                    rows.append([
                        f"{elapsed_s:.2f}",
                        f"{sound_heard_s:.2f}",
                        f"{level_dbfs:.1f}",
                        "" if background_dbfs is None else f"{background_dbfs:.1f}",
                        int(noise_starts),
                        "" if agc_gain is None else f"{agc_gain:.3f}",
                    ])
        finally:
            mini.media.stop_recording()

    with open(path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["clock_s", "sound_heard_s", "level_dbfs", "background_dbfs", "noise_starts",
                         "agc_gain"])
        writer.writerows(rows)
    print(f"Saved {path}: {len(rows)} stretches, {sound_heard_s:.1f} s of sound")
    plot(path, rows)


def plot(path: str, rows) -> None:
    t = [float(r[0]) for r in rows]
    level = [float(r[2]) for r in rows]
    background = [float(r[3]) if r[3] else float("nan") for r in rows]
    starts = [float(r[0]) for r in rows if r[4]]
    gain_db = [20 * math.log10(float(r[5])) if r[5] else float("nan") for r in rows]
    level_without_gain = [lv - g for lv, g in zip(level, gain_db)]

    fig, (ax, ax_gain) = plt.subplots(2, 1, sharex=True, figsize=(14, 8))
    ax_gain.plot(t, gain_db, label="automatic gain (dB)")
    ax_gain.set_ylabel("dB")
    ax_gain.grid(True)
    ax_gain.legend(loc="lower right")
    ax.plot(t, level_without_gain, linewidth=0.7, color="grey", label="level minus gain (dBFS)")
    ax.plot(t, level, linewidth=0.7, label="level (dBFS)")
    ax.plot(t, background, label="background (dBFS)")
    start_db = SuddenNoiseDetector.START_THRESHOLD_DB
    ax.plot(t, [b + start_db for b in background], "--",
            label=f"start threshold (background + {start_db:.0f} dB)")
    for s in starts:
        ax.axvline(s, color="red", alpha=0.4)
    for second, text in INSTRUCTIONS.items():
        if not text.startswith(">>>"):
            continue
        ax.annotate(text[8:], (second, -5), fontsize=7, rotation=90, va="top")
    ax_gain.set_xlabel("clock (s), as printed on screen")
    ax.set_ylabel("dBFS")
    ax.set_ylim(-100, 0)
    ax.grid(True)
    ax.legend(loc="lower right")
    out = path.replace(".csv", ".png")
    fig.savefig(out, dpi=120)
    print(f"Saved {out} (red lines: where the detector says 'sudden noise')")


if __name__ == "__main__":
    record(sys.argv[1])
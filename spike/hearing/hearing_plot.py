"""Spike: plot a recording made by hearing_record.py: loudness, then direction.

Throwaway code, never merged. Usage:
    uv run --with matplotlib python spike/hearing/hearing_plot.py spike/hearing/claps
"""

import csv
import sys
import wave

import matplotlib.pyplot as plt
import numpy as np

WINDOW_S = 0.02  # loudness is measured over 20 ms windows


def main(prefix: str) -> None:
    with wave.open(f"{prefix}.wav") as w:
        rate = w.getframerate()
        channels = w.getnchannels()
        audio = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16)
    audio = audio.reshape(-1, channels) / 32768
    mono = audio.mean(axis=1)

    n = int(rate * WINDOW_S)
    k = len(mono) // n
    rms = np.sqrt(np.mean(mono[: k * n].reshape(k, n) ** 2, axis=1))
    loudness_db = 20 * np.log10(rms + 1e-9)  # dBFS: 0 = loudest possible
    t = np.arange(k) * WINDOW_S

    with open(f"{prefix}_doa.csv") as f:
        rows = list(csv.DictReader(f))
    t_doa = np.array([float(r["t_s"]) for r in rows])
    angle_deg = np.rad2deg([float(r["angle_rad"]) for r in rows])
    speech = np.array([r["speech_detected"] == "True" for r in rows], dtype=bool)

    fig, (ax_l, ax_d) = plt.subplots(2, 1, sharex=True, figsize=(12, 7))
    ax_l.plot(t, loudness_db)
    ax_l.set_ylabel("loudness (dBFS, 20 ms windows)")
    if len(rows):
        ax_d.plot(t_doa[~speech], angle_deg[~speech], ".", label="no speech")
        ax_d.plot(t_doa[speech], angle_deg[speech], "o", label="speech detected")
        ax_d.legend(loc="upper right")
    ax_d.set_ylabel("direction (deg)\n0 left, 90 front, 180 right")
    ax_d.set_ylim(-5, 185)
    ax_d.set_xlabel("time (s)")
    for ax in (ax_l, ax_d):
        ax.grid(True)
    fig.suptitle(prefix)
    fig.savefig(f"{prefix}.png", dpi=120)
    print(f"Saved {prefix}.png")
    print(f"loudness: median {np.median(loudness_db):.1f} dBFS, max {loudness_db.max():.1f} dBFS")


if __name__ == "__main__":
    main(sys.argv[1])

"""Spike: record what the microphones hear, and where the robot thinks it came from.

Throwaway code, never merged. The app must NOT be running. Usage:
    uv run python spike/hearing/hearing_record.py spike/hearing/claps 40
writes claps.wav (what the robot heard) and claps_doa.csv (sound direction).

The direction comes from the daemon's HTTP API: from a laptop, the SDK's
get_DoA() looks for the microphone chip over USB on the laptop itself, and
finds nothing. On the robot, get_DoA() would work directly.
"""

import csv
import json
import sys
import time
import urllib.request
import wave

import numpy as np
from reachy_mini import ReachyMini

DOA_URL = "http://reachy-mini.local:8000/api/state/doa"
DOA_PERIOD_S = 0.1


def read_doa() -> dict | None:
    """Return {"angle": rad, "speech_detected": bool}, or None if unavailable."""
    try:
        with urllib.request.urlopen(DOA_URL, timeout=0.2) as response:
            return json.load(response)
    except OSError:
        return None


def main(prefix: str, duration_s: float) -> None:
    chunks = []
    doa_rows = []
    with ReachyMini() as mini:
        rate = mini.media.get_input_audio_samplerate()
        mini.media.start_recording()
        t0 = time.monotonic()
        next_doa_s = 0.0
        last_second = -1
        try:
            while (t := time.monotonic() - t0) < duration_s:
                if int(t) != last_second:  # a clock to time your actions
                    last_second = int(t)
                    print(f"{last_second} s")
                sample = mini.media.get_audio_sample()
                if sample is not None:
                    chunks.append(sample)
                if t >= next_doa_s:
                    next_doa_s += DOA_PERIOD_S
                    doa = read_doa()
                    if doa is not None:
                        doa_rows.append([f"{t:.3f}", doa["angle"], doa["speech_detected"]])
                time.sleep(0.005)
        finally:
            mini.media.stop_recording()

    audio = np.concatenate(chunks) if chunks else np.zeros((0, 2), np.float32)
    with wave.open(f"{prefix}.wav", "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)  # 16-bit
        w.setframerate(rate)
        w.writeframes((np.clip(audio, -1, 1) * 32767).astype(np.int16).tobytes())
    with open(f"{prefix}_doa.csv", "w", newline="") as f:
        csv.writer(f).writerows([["t_s", "angle_rad", "speech_detected"], *doa_rows])
    print(f"{len(audio) / rate:.1f} s of audio at {rate} Hz, {len(doa_rows)} DoA readings")


if __name__ == "__main__":
    main(sys.argv[1], float(sys.argv[2]))

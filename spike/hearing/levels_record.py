"""Record how loud the room is, 20 ms at a time, to tune the sudden-noise thresholds.

Throwaway code, never merged. The app must NOT be running: it would take the
microphones. Usage, with a scenario name from SCENARIOS:
    uv run python spike/hearing/levels_record.py quiet_claps

Follow the instructions printed on screen. It writes spike/hearing/<scenario>.csv,
one row per frame. No sound is kept, only how loud it was. It only records:
hearing_replay.py judges a recording, with any thresholds, as often as needed.
"""

import csv
import json
import sys
import time
import urllib.request
from pathlib import Path

from reachy_mini import ReachyMini

from reachy_alive.brain.sensory_cortex.hearing.hearing_sense import HearingSense
from reachy_alive.shared_state import SharedState

GAIN_URL = "http://reachy-mini.local:8000/api/audio/config/parameter/PP_AGCGAIN"
GAIN_PERIOD_S = 0.5

# The microphones' automatic gain rises in silence: each scenario starts with a
# minute of it, like a quiet room before a clap.
SETTLE_S = 60

CLAPS_SOFT_TO_HARD = {
    SETTLE_S - 1: "get ready to clap, 1 m from the robot",
    SETTLE_S: ">>> NOW: clap very softly",
    SETTLE_S + 4: ">>> NOW: clap very softly",
    SETTLE_S + 8: ">>> NOW: clap softly",
    SETTLE_S + 12: ">>> NOW: clap softly",
    SETTLE_S + 16: ">>> NOW: clap normally",
    SETTLE_S + 20: ">>> NOW: clap normally",
    SETTLE_S + 24: ">>> NOW: clap hard",
    SETTLE_S + 28: ">>> NOW: clap hard",
    SETTLE_S + 32: "Done",
}

# What to do, and when: printed when the clock reaches each second. A scenario
# ends at its last instruction.
SCENARIOS = {
    "quiet_claps": {
        0: "Quiet room. Hands off the keyboard: silence for one minute",
        **CLAPS_SOFT_TO_HARD,
    },
    "tv_claps": {
        0: "TV on, normal volume. Hands off the keyboard: one minute of TV only",
        **CLAPS_SOFT_TO_HARD,
    },
    "talk": {
        0: "Quiet room. Hands off the keyboard: silence for one minute",
        SETTLE_S - 1: "get ready to talk, 1 m from the robot",
        SETTLE_S: ">>> NOW: talk normally, short sentences with pauses",
        SETTLE_S + 15: "Silence",
        SETTLE_S + 19: "get ready to talk LOUDLY, 1 m from the robot",
        SETTLE_S + 20: ">>> NOW: talk loudly, short sentences with pauses",
        SETTLE_S + 35: "Silence",
        SETTLE_S + 40: "Done",
    },
}

COLUMNS = ["clock_s", "time_listened_s", "level_dbfs", "agc_gain"]


def read_agc_gain() -> float | None:
    """Return the microphones' automatic gain (a factor, not dB), or None if unavailable."""
    try:
        with urllib.request.urlopen(GAIN_URL, timeout=0.2) as response:
            return float(json.load(response)["values"][0])
    except (OSError, KeyError, ValueError):
        return None


def record(scenario: str) -> None:
    """Follow the scenario on screen, and save the level of every frame heard meanwhile."""
    instructions = SCENARIOS[scenario]
    duration_s = max(instructions)  # the last instruction ends the scenario
    rows = []
    with ReachyMini() as mini:
        # The app's own sense: the levels are exactly what the detector reads.
        sense = HearingSense(mini, SharedState())
        started_at = time.monotonic()
        last_second = -1
        agc_gain = read_agc_gain()
        next_gain_read_s = GAIN_PERIOD_S
        try:
            while True:
                clock_s = time.monotonic() - started_at
                if int(clock_s) != last_second:  # a clock to time your actions
                    last_second = int(clock_s)
                    print(f"{last_second:3d} s  {instructions.get(last_second, '')}")
                    if last_second >= duration_s:
                        break
                if clock_s >= next_gain_read_s:
                    next_gain_read_s += GAIN_PERIOD_S
                    agc_gain = read_agc_gain() or agc_gain
                features = sense.perceive(time.monotonic())
                if features is None:
                    continue  # no full frame yet
                rows.append(
                    [
                        f"{clock_s:.2f}",
                        f"{features.time_listened_s:.2f}",
                        f"{features.level_dbfs:.1f}",
                        "" if agc_gain is None else f"{agc_gain:.3f}",
                    ]
                )
        finally:
            mini.media.stop_recording()

    path = Path(__file__).parent / f"{scenario}.csv"
    with open(path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(COLUMNS)
        writer.writerows(rows)
    print(f"Saved {path}: {len(rows)} frames")


if __name__ == "__main__":
    record(sys.argv[1])

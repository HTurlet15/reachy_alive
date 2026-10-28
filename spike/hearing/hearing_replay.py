"""Replay a recording through the sudden-noise detector, with any thresholds, and plot it.

Throwaway code, never merged. Usage, after levels_record.py made the CSV:
    uv run --with matplotlib python spike/hearing/hearing_replay.py quiet_claps --start 25

Runs main's own SuddenNoiseDetector over spike/hearing/<scenario>.csv. It
prints how far each action stood above the background, and writes
spike/hearing/<scenario>_start<S>_end<E>.png.
"""

import argparse
import csv
import math
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # draw to a file only: no window, nothing to wait for
import matplotlib.pyplot as plt  # noqa: E402
from levels_record import SCENARIOS  # noqa: E402

from reachy_alive.brain.sensory_cortex.detector import Background, SchmittTrigger  # noqa: E402
from reachy_alive.brain.sensory_cortex.hearing.hearing_features import (  # noqa: E402
    HearingFeatures,
)
from reachy_alive.brain.sensory_cortex.hearing.sudden_noise_detector import (  # noqa: E402
    SuddenNoiseDetector,
)

# How long after an instruction its sound is looked for: your reaction time, then the sound.
ACTION_WINDOW_S = 2.0
ACTION_PREFIX = ">>> NOW: "  # how levels_record.py marks what to do, and when


class SuddenNoiseLog:
    """Stands in for HearingFacts: keeps every sudden noise, not only the last one."""

    def __init__(self) -> None:
        """Start with no sudden noise."""
        self.times: list[float] = []

    def record_sudden_noise(self, at: float) -> None:
        """Keep a sudden noise, dated on the recording's clock."""
        self.times.append(at)


def read_recording(scenario: str) -> list[dict[str, float | None]]:
    """Return the rows of a recording, as numbers: agc_gain is None where unknown."""
    with open(Path(__file__).parent / f"{scenario}.csv") as f:
        return [
            {
                "clock_s": float(row["clock_s"]),
                "time_listened_s": float(row["time_listened_s"]),
                "level_dbfs": float(row["level_dbfs"]),
                "agc_gain": float(row["agc_gain"]) if row["agc_gain"] else None,
            }
            for row in csv.DictReader(f)
        ]


def replay(rows, start_db: float, end_db: float):
    """Run the detector over the rows, and follow the height above the background beside it.

    Returns the background and height of every row, when a loud sound
    started (habituation or not), and when the detector recorded a sudden noise.
    """
    SuddenNoiseDetector.START_THRESHOLD_DB = start_db
    SuddenNoiseDetector.END_THRESHOLD_DB = end_db
    log = SuddenNoiseLog()
    detector = SuddenNoiseDetector(log)

    # The same mechanisms as the detector, followed beside it: the detector keeps its own private.
    background = Background(time_constant_s=SuddenNoiseDetector.BACKGROUND_TIME_CONSTANT_S)
    loud_sound = SchmittTrigger(on_threshold=start_db, off_threshold=end_db)
    backgrounds, heights, loud_sound_starts = [], [], []
    for row in rows:
        height_db = background.height_of(row["level_dbfs"])
        backgrounds.append(row["level_dbfs"] - height_db)
        heights.append(height_db)
        if loud_sound.would_turn_on(height_db):
            loud_sound_starts.append(row["clock_s"])
        background.follow(row["time_listened_s"], row["level_dbfs"])
        loud_sound.update(row["time_listened_s"], height_db)

        detector.update(
            HearingFeatures(
                perceived_at=row["clock_s"],  # sudden noises dated on the on-screen clock
                time_listened_s=row["time_listened_s"],
                level_dbfs=row["level_dbfs"],
                robot_moving_itself=False,
            )
        )
    return backgrounds, heights, loud_sound_starts, log.times


def print_actions(scenario: str, rows, heights, sudden_noises, start_db: float) -> None:
    """Print, for each action, its peak height above the background and what the detector said."""
    for second, text in SCENARIOS[scenario].items():
        if not text.startswith(ACTION_PREFIX):
            continue
        in_window = [
            height
            for row, height in zip(rows, heights, strict=True)
            if second <= row["clock_s"] < second + ACTION_WINDOW_S
        ]
        peak_db = max(in_window, default=-math.inf)
        heard = any(second <= t < second + ACTION_WINDOW_S for t in sudden_noises)
        verdict = "sudden noise" if heard else ("loud, expected" if peak_db >= start_db else "-")
        action = text.removeprefix(ACTION_PREFIX)
        print(f"{second:3d} s  {action:<45} peak {peak_db:5.1f} dB  {verdict}")


def plot(
    scenario: str,
    rows,
    backgrounds,
    heights,
    loud_sound_starts,
    sudden_noises,
    start_db: float,
    end_db: float,
) -> Path:
    """Draw the level, the height above the background, and the gain. Return the image path."""
    clock = [row["clock_s"] for row in rows]
    gain_db = [20 * math.log10(row["agc_gain"]) if row["agc_gain"] else math.nan for row in rows]
    fig, (ax_level, ax_height, ax_gain) = plt.subplots(3, 1, sharex=True, figsize=(14, 10))

    ax_level.plot(clock, [row["level_dbfs"] for row in rows], linewidth=0.7, label="level")
    ax_level.plot(clock, backgrounds, label="background")
    ax_level.set_ylabel("dBFS")
    ax_level.set_ylim(-100, 0)

    ax_height.plot(clock, heights, linewidth=0.7, label="height above background")
    ax_height.axhline(start_db, color="red", linestyle="--", label=f"start ({start_db:g} dB)")
    ax_height.axhline(end_db, color="grey", linestyle="--", label=f"end ({end_db:g} dB)")
    ax_height.plot(
        loud_sound_starts,
        [start_db] * len(loud_sound_starts),
        "o",
        color="orange",
        label="loud sound starts",
    )
    for t in sudden_noises:
        ax_height.axvline(t, color="red", alpha=0.4)
    ax_height.set_ylabel("dB")

    ax_gain.plot(clock, gain_db, label="automatic gain")
    ax_gain.set_ylabel("dB")
    ax_gain.set_xlabel("clock (s), as printed on screen")

    for second, text in SCENARIOS[scenario].items():
        if text.startswith(ACTION_PREFIX):
            ax_height.annotate(
                text.removeprefix(ACTION_PREFIX),
                (second, ax_height.get_ylim()[1]),
                fontsize=7,
                rotation=90,
                va="top",
            )
    for ax in (ax_level, ax_height, ax_gain):
        ax.grid(True)
        ax.legend(loc="upper left")  # the scenarios start with silence: nothing there
    fig.suptitle(f"{scenario}: red lines are sudden noises")
    path = Path(__file__).parent / f"{scenario}_start{start_db:g}_end{end_db:g}.png"
    fig.savefig(path, dpi=120)
    return path


def main() -> None:
    """Replay one recording with the thresholds given, print the actions, save the plot."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("scenario", choices=SCENARIOS)
    parser.add_argument("--start", type=float, default=SuddenNoiseDetector.START_THRESHOLD_DB)
    parser.add_argument("--end", type=float, default=SuddenNoiseDetector.END_THRESHOLD_DB)
    args = parser.parse_args()

    rows = read_recording(args.scenario)
    backgrounds, heights, loud_sound_starts, sudden_noises = replay(rows, args.start, args.end)
    print_actions(args.scenario, rows, heights, sudden_noises, args.start)
    path = plot(
        args.scenario,
        rows,
        backgrounds,
        heights,
        loud_sound_starts,
        sudden_noises,
        args.start,
        args.end,
    )
    print(f"{len(sudden_noises)} sudden noises, {len(loud_sound_starts)} loud sound starts")
    print(f"Saved {path}")


if __name__ == "__main__":
    main()

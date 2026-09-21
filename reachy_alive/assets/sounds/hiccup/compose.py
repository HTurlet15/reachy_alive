"""Compose hiccup_full.wav from its parts."""

from pathlib import Path

from reachy_alive.scripts.compose_sound import concatenate

HERE = Path(__file__).resolve().parent

concatenate(
    [
        (str(HERE / "hiccup.wav"), 2),
        (str(HERE / "hiccup.wav"), 2),
        (str(HERE / "hiccup.wav"), 0.5),
        (str(HERE / "complaining.wav"), 2.5),
        (str(HERE / "hiccup.wav"), 0.0),
    ],
    str(HERE / "hiccup_full.wav"),
)
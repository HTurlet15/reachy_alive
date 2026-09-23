"""Compose hiccup_full.wav from its parts."""

from pathlib import Path

from reachy_alive.scripts.compose_sound import concatenate

HERE = Path(__file__).resolve().parent

concatenate(
    [
        (str(HERE / "inhale1.wav"), 0.5),
        (str(HERE / "inhale2.wav"), 0.5),
        (str(HERE / "inhale3.wav"), 0.5),
        (str(HERE / "sneeze.wav"), 0.5),
        (str(HERE / "relief.wav"),0),
    ],
    str(HERE / "sneezing.wav"),
)


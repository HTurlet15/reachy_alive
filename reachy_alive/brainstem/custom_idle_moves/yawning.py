# reachy_alive/brainstem/custom_idle_moves/yawning.py
"""Yawn-like gesture, using the closest available library move.

Checked via emotions.list_moves() on 2026-07-26: no exact "yawn" move
exists in the library. "tired1" is the closest available stand-in.
Replace with a custom recorded move later if a real yawn is wanted.
"""

from reachy_alive.library_move import LibraryMove


class Yawning(LibraryMove):
    """Plays a tiredness gesture as a stand-in for yawning."""

    def __init__(self) -> None:
        super().__init__(move_name="tired1")
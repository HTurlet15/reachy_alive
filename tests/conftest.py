# tests/conftest.py
"""Shared pytest fixtures."""

from unittest.mock import MagicMock

import numpy as np
import pytest


@pytest.fixture
def fake_reachy_mini():
    """A mock standing in for a connected ReachyMini instance.

    Records calls to goto_target/set_target/play_move without touching
    any real hardware, so behavior/gesture tests can assert on what was
    sent, with no physical robot required.
    """
    return MagicMock()


class FakeRecording:
    """Stands in for a Marionette recording: a still head, a turned body.

    Like the SDK's RecordedMove, evaluate() refuses any t at or past the
    last frame.
    """

    HEAD = np.eye(4)
    BODY_YAW_RAD = 0.3

    def __init__(self, last_frame_s: float = 100.0) -> None:
        self.timestamps = [0.0, last_frame_s]
        self.evaluated_at: list[float] = []

    @property
    def duration(self) -> float:
        return self.timestamps[-1]

    def evaluate(self, t: float) -> tuple[np.ndarray, np.ndarray, float]:
        if t >= self.timestamps[-1]:
            raise Exception("Tried to evaluate recorded move beyond its duration.")
        self.evaluated_at.append(t)
        return self.HEAD, np.zeros(2), self.BODY_YAW_RAD


@pytest.fixture
def fake_recording():
    """A recording long enough for any move; shorten it with ``timestamps``."""
    return FakeRecording()


@pytest.fixture
def fake_library(fake_recording):
    """A recorded-moves library that returns ``fake_recording`` for any name."""
    library = MagicMock()
    library.get.return_value = fake_recording
    return library
"""Shared pytest fixtures."""

import queue
from unittest.mock import MagicMock

import numpy as np
import pytest

from reachy_alive.control.action_selector import ActionSelector
from reachy_alive.control.robot_controller import RobotController
from reachy_alive.moves.base import Move
from reachy_alive.moves.robot_sounds import upload_sounds
from reachy_alive.shared_state import SharedState


@pytest.fixture
def fake_reachy_mini():
    """A mock standing in for a connected ReachyMini instance.

    Records calls to goto_target/set_target/play_move without touching
    any real hardware, so move tests can assert on what was
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

    def __init__(self) -> None:
        self.timestamps = [0.0, 100.0]
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


class NoIdleMoves:
    """Stands in for IdleManager: proposes nothing."""

    def propose(self, resting_for_s):
        return None


@pytest.fixture
def play(fake_reachy_mini):
    """Play a move on ``fake_reachy_mini`` as the app does, on a simulated clock.

    The ActionSelector cuts it into ticks and the RobotController sends them,
    every 20 ms, through the move and its way back to neutral, without
    waiting. Returns the commands sent, in order.
    """

    def play_move(move, tick_s=0.02):
        state = SharedState()
        requests = queue.Queue()
        requests.put(move)
        selector = ActionSelector(NoIdleMoves(), requests, state)
        controller = RobotController(selector, upload_sounds([move], fake_reachy_mini))
        commands = []
        t = 0.0
        while (command := selector.decide(t)).from_move:  # until breathing again
            controller._execute(command, fake_reachy_mini, state)
            commands.append(command)
            t += tick_s
        return commands

    return play_move


class StillMove(Move):
    """A move that holds one pose, to test whoever plays moves."""

    HEAD = np.eye(4)
    ANTENNAS = [0.3, -0.3]
    BODY_YAW_RAD = 0.2

    def __init__(self, duration: float = 0.1, sound_cues=()) -> None:
        self.duration = duration
        self.sound_cues = tuple(sound_cues)
        self.draws = 0

    def draw_variations(self) -> None:
        self.draws += 1

    def evaluate(self, t):
        return self.HEAD, self.ANTENNAS, self.BODY_YAW_RAD

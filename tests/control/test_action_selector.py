"""Unit tests for ActionSelector."""

import queue
from unittest.mock import MagicMock

import numpy as np

from reachy_alive.control.action_selector import ActionSelector
from reachy_alive.control.commands import HoldPose, PlayMove
from reachy_alive.moves.base import NEUTRAL_ANTENNAS_RAD
from reachy_alive.shared_state import SharedState


def idle_proposing(move):
    """An IdleManager that proposes ``move`` (None: nothing) on every tick."""
    idle_manager = MagicMock()
    idle_manager.propose.return_value = move
    return idle_manager


def decide(selector, fake_reachy_mini, t=1.0):
    """Let the selector decide once, at t."""
    return selector.decide(t)


def test_plays_the_idle_move_idle_proposes(fake_reachy_mini):
    move = MagicMock()
    selector = ActionSelector(idle_proposing(move), queue.Queue(), SharedState())

    command = decide(selector, fake_reachy_mini)

    assert isinstance(command, PlayMove)
    assert command.move is move


def test_breathes_when_nobody_proposes_a_move(fake_reachy_mini):
    selector = ActionSelector(idle_proposing(None), queue.Queue(), SharedState())

    command = decide(selector, fake_reachy_mini)

    assert isinstance(command, HoldPose)


def test_a_requested_move_wins_over_idle(fake_reachy_mini):
    idle_manager = idle_proposing(MagicMock())
    requests = queue.Queue()
    move = MagicMock()
    requests.put(move)
    selector = ActionSelector(idle_manager, requests, SharedState())

    command = decide(selector, fake_reachy_mini)

    assert isinstance(command, PlayMove)
    assert command.move is move
    idle_manager.propose.assert_not_called()


def test_only_the_latest_request_plays(fake_reachy_mini):
    requests = queue.Queue()
    first, latest = MagicMock(), MagicMock()
    requests.put(first)
    requests.put(latest)
    selector = ActionSelector(idle_proposing(None), requests, SharedState())

    command = decide(selector, fake_reachy_mini)

    assert command.move is latest
    assert requests.empty()


def assert_neutral(command):
    """Check that a breathing command is the neutral pose, where breathing starts."""
    np.testing.assert_allclose(command.head, np.eye(4), atol=1e-9)
    np.testing.assert_allclose(command.antennas, NEUTRAL_ANTENNAS_RAD)


def test_breathing_starts_from_neutral(fake_reachy_mini):
    selector = ActionSelector(idle_proposing(None), queue.Queue(), SharedState())

    assert_neutral(decide(selector, fake_reachy_mini, t=7.3))


def test_breathing_keeps_its_own_rhythm_between_moves(fake_reachy_mini):
    selector = ActionSelector(idle_proposing(None), queue.Queue(), SharedState())
    decide(selector, fake_reachy_mini, t=5.0)

    command = decide(selector, fake_reachy_mini, t=6.0)  # 1 s into the breath

    assert not np.allclose(command.antennas, NEUTRAL_ANTENNAS_RAD)


def test_breathing_restarts_from_neutral_after_an_idle_move(fake_reachy_mini):
    idle_manager = idle_proposing(None)
    selector = ActionSelector(idle_manager, queue.Queue(), SharedState())
    decide(selector, fake_reachy_mini, t=5.0)  # breathing starts
    idle_manager.propose.return_value = MagicMock()
    decide(selector, fake_reachy_mini, t=6.0)  # an idle move plays
    idle_manager.propose.return_value = None

    assert_neutral(decide(selector, fake_reachy_mini, t=12.3))


def test_breathing_restarts_from_neutral_after_a_requested_move(fake_reachy_mini):
    requests = queue.Queue()
    selector = ActionSelector(idle_proposing(None), requests, SharedState())
    decide(selector, fake_reachy_mini, t=5.0)  # breathing starts
    requests.put(MagicMock())
    decide(selector, fake_reachy_mini, t=6.0)  # the requested move plays

    assert_neutral(decide(selector, fake_reachy_mini, t=12.3))

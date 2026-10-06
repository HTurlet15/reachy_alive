"""Unit tests for ActionSelector."""

import queue
from unittest.mock import MagicMock

from reachy_alive.control.action_selector import ActionSelector
from reachy_alive.control.commands import PlayMove
from reachy_alive.shared_state import SharedState


def decide(selector, fake_reachy_mini):
    return selector.decide(t=1.0, shared_state=SharedState(), reachy_mini=fake_reachy_mini)


def test_follows_idle_when_nothing_is_requested(fake_reachy_mini):
    idle_manager = MagicMock()
    selector = ActionSelector(idle_manager, queue.Queue())

    command = decide(selector, fake_reachy_mini)

    assert command is idle_manager.decide.return_value
    idle_manager.interrupt.assert_not_called()


def test_a_requested_move_wins_over_idle(fake_reachy_mini):
    idle_manager = MagicMock()
    requests = queue.Queue()
    move = MagicMock()
    requests.put(move)
    selector = ActionSelector(idle_manager, requests)

    command = decide(selector, fake_reachy_mini)

    assert isinstance(command, PlayMove)
    assert command.move is move
    idle_manager.decide.assert_not_called()
    idle_manager.interrupt.assert_called_once()


def test_only_the_latest_request_plays(fake_reachy_mini):
    requests = queue.Queue()
    first, latest = MagicMock(), MagicMock()
    requests.put(first)
    requests.put(latest)
    selector = ActionSelector(MagicMock(), requests)

    command = decide(selector, fake_reachy_mini)

    assert command.move is latest
    assert requests.empty()
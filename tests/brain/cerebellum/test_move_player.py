"""Tests for MovePlayer: every pose played where the head points."""

import math

import numpy as np
import pytest

from reachy_alive.brain.basal_ganglia.proposal import Direction, Proposal
from reachy_alive.brain.cerebellum.move_player import MovePlayer
from reachy_alive.moves.base import ReturningToNeutral
from reachy_alive.shared_state import CommandedPose, SharedState
from tests.conftest import StillMove

LEFT = math.radians(45)
LOOK_LEFT = Direction(yaw_rad=LEFT, duration_s=0.0)
TICK_S = 0.02


def turned_by(yaw_rad):
    """The 4x4 turn around the vertical axis, to compare heads with."""
    cos, sin = math.cos(yaw_rad), math.sin(yaw_rad)
    return np.array([[cos, -sin, 0, 0], [sin, cos, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])


def yaw_of(head):
    """The head's turn around the vertical axis, for a pose with no roll or pitch."""
    return math.atan2(head[1, 0], head[0, 0])


def play(first_proposal, until_s=3.0):
    """Tick a MovePlayer on a simulated clock, recording each pose as the controller does.

    first_proposal is handed over on the first tick only, like any order.
    """
    state = SharedState()
    player = MovePlayer(state)
    commands = []
    for i in range(round(until_s / TICK_S)):
        now = i * TICK_S
        command = player.tick(now, first_proposal if i == 0 else None)
        state.record_commanded_pose(
            CommandedPose(
                at=now, head=command.head, antennas=command.antennas, body_yaw=command.body_yaw
            )
        )
        commands.append(command)
    return commands


def test_looking_at_the_front_changes_nothing():
    command = MovePlayer(SharedState()).tick(
        0.0, Proposal(source="test", move_to_start=StillMove(duration=1.0))
    )

    np.testing.assert_allclose(command.head, StillMove.HEAD)
    assert command.body_yaw == pytest.approx(StillMove.BODY_YAW_RAD)


def test_breathing_is_played_where_the_head_points():
    in_front = play(None, until_s=1.0)
    looking_left = play(Proposal(source="test", direction=LOOK_LEFT), until_s=1.0)

    for front, left in zip(in_front, looking_left, strict=True):
        np.testing.assert_allclose(left.head, turned_by(LEFT) @ front.head)
        np.testing.assert_allclose(left.antennas, front.antennas)
        assert left.body_yaw == pytest.approx(0.0)


def test_a_move_is_played_where_the_head_points():
    move = StillMove(duration=1.0)
    commands = play(Proposal(source="test", move_to_start=move, direction=LOOK_LEFT))

    move_ticks = commands[:50]
    assert all(command.from_move for command in move_ticks)
    for command in move_ticks:
        np.testing.assert_allclose(command.head, turned_by(LEFT) @ StillMove.HEAD)
        assert command.body_yaw == pytest.approx(StillMove.BODY_YAW_RAD)


def test_the_way_back_starts_from_the_last_pose_sent_without_a_jump():
    move = StillMove(duration=1.0)
    commands = play(Proposal(source="test", move_to_start=move, direction=LOOK_LEFT))

    last_of_the_move, first_of_the_way_back = commands[49], commands[50]
    np.testing.assert_allclose(first_of_the_way_back.head, last_of_the_move.head, atol=1e-9)
    assert first_of_the_way_back.body_yaw == pytest.approx(last_of_the_move.body_yaw)


def test_after_the_way_back_the_head_still_points_in_the_direction():
    move = StillMove(duration=1.0)
    commands = play(Proposal(source="test", move_to_start=move, direction=LOOK_LEFT))

    breathing_again = commands[50 + round(ReturningToNeutral.DURATION_S / TICK_S)]
    assert not breathing_again.from_move
    assert yaw_of(breathing_again.head) == pytest.approx(LEFT)
    assert breathing_again.body_yaw == pytest.approx(0.0)

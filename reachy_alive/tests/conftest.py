# reachy_alive/tests/conftest.py
"""Shared pytest fixtures."""

from unittest.mock import MagicMock

import pytest
from reachy_mini.utils import create_head_pose

from reachy_alive.moves.base import NEUTRAL_ANTENNAS_RAD


@pytest.fixture
def fake_reachy_mini():
    """A mock standing in for a connected ReachyMini instance.

    Records calls to goto_target/set_target/play_move without touching
    any real hardware, so behavior/gesture tests can assert on what was
    sent, with no physical robot required. It reports a neutral pose by
    default; a test that needs the robot to end elsewhere overrides
    get_current_head_pose or get_present_antenna_joint_positions.
    """
    reachy_mini = MagicMock()
    reachy_mini.get_current_head_pose.return_value = create_head_pose()
    reachy_mini.get_present_antenna_joint_positions.return_value = NEUTRAL_ANTENNAS_RAD
    return reachy_mini
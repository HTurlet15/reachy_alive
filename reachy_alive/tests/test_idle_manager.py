# reachy_alive/tests/test_idle_manager.py
"""Unit tests for IdleManager."""

import time

from reachy_alive.shared_state import SharedState
from reachy_alive.brainstem.idle_manager import IdleManager


def test_returns_pose_when_nothing_external_is_active():
    state = SharedState()
    manager = IdleManager()

    pose = manager.get_pose(t=1.0, shared_state=state)

    assert pose is not None
    head_pose, antennas_rad = pose
    assert head_pose is not None
    assert antennas_rad.shape == (2,)


def test_returns_none_when_external_command_is_active():
    state = SharedState()
    state.last_external_command_at = time.time()
    manager = IdleManager()

    pose = manager.get_pose(t=1.0, shared_state=state)

    assert pose is None
# reachy_alive/tests/test_idle_manager.py
"""Unit tests for IdleManager."""

from reachy_alive.brainstem.idle_manager import IdleManager
from reachy_alive.shared_state import SharedState


def test_returns_breathing_pose_when_not_time_for_a_gesture(fake_reachy_mini):
    state = SharedState()
    state.mark_activity()
    manager = IdleManager(gesture_interval_range_s=(100.0, 100.0))

    pose = manager.get_pose(t=1.0, shared_state=state, reachy_mini=fake_reachy_mini)

    assert pose is not None
    head_pose, antennas_rad = pose
    assert head_pose is not None
    assert antennas_rad.shape == (2,)
    fake_reachy_mini.play_move.assert_not_called()
    fake_reachy_mini.goto_target.assert_not_called()


def test_triggers_a_gesture_and_resets_activity(fake_reachy_mini, monkeypatch):
    state = SharedState()
    manager = IdleManager(gesture_interval_range_s=(0.0, 0.0))
    forced_behavior = manager._behaviors[0]
    monkeypatch.setattr("random.choice", lambda seq: forced_behavior)

    pose = manager.get_pose(t=1.0, shared_state=state, reachy_mini=fake_reachy_mini)

    assert pose is None
    assert state.seconds_since_last_activity() < 0.1
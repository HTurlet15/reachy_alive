# reachy_alive/tests/conftest.py
"""Shared pytest fixtures."""

from unittest.mock import MagicMock

import pytest


@pytest.fixture
def fake_reachy_mini():
    """A mock standing in for a connected ReachyMini instance.

    Records calls to goto_target/set_target/play_move without touching
    any real hardware, so behavior/gesture tests can assert on what was
    sent, with no physical robot required.
    """
    return MagicMock()
"""Unit tests for the app page's routes."""

import queue
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from reachy_alive.routes import create_router
from reachy_alive.shared_state import DEFAULT_IDLE_MOVE_INTERVAL_RANGE_S, SharedState

INTERVAL_URL = "/settings/idle-move-interval"


@pytest.fixture
def sneezing():
    return MagicMock()


@pytest.fixture
def move_requests():
    return queue.Queue()


@pytest.fixture
def shared_state():
    return SharedState()


@pytest.fixture
def client(sneezing, move_requests, shared_state):
    """A client for an app serving only the page's routes."""
    app = FastAPI()
    app.include_router(create_router({"sneezing": sneezing}, move_requests, shared_state))
    return TestClient(app)


def test_lists_the_move_names(client):
    response = client.get("/moves")

    assert response.status_code == 200
    assert response.json() == ["sneezing"]


def test_a_requested_move_is_queued(client, move_requests, sneezing):
    response = client.post("/moves/sneezing/play")

    assert response.status_code == 202
    assert move_requests.get_nowait() is sneezing


def test_an_unknown_move_is_404_and_queues_nothing(client, move_requests):
    response = client.post("/moves/nope/play")

    assert response.status_code == 404
    assert move_requests.empty()


def test_reads_the_idle_move_interval(client):
    response = client.get(INTERVAL_URL)

    min_s, max_s = DEFAULT_IDLE_MOVE_INTERVAL_RANGE_S
    assert response.status_code == 200
    assert response.json() == {"min_s": min_s, "max_s": max_s}


def test_changes_the_idle_move_interval(client, shared_state):
    response = client.put(INTERVAL_URL, json={"min_s": 5, "max_s": 10})

    assert response.status_code == 200
    assert shared_state.idle_move_interval_range_s() == (5.0, 10.0)


def test_rejects_a_min_above_the_max(client, shared_state):
    response = client.put(INTERVAL_URL, json={"min_s": 10, "max_s": 5})

    assert response.status_code == 422
    assert shared_state.idle_move_interval_range_s() == DEFAULT_IDLE_MOVE_INTERVAL_RANGE_S


def test_rejects_an_interval_out_of_bounds(client, shared_state):
    response = client.put(INTERVAL_URL, json={"min_s": 1, "max_s": 10})

    assert response.status_code == 422
    assert shared_state.idle_move_interval_range_s() == DEFAULT_IDLE_MOVE_INTERVAL_RANGE_S
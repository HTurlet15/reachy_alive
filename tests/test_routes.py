"""Unit tests for the app page's routes."""

import logging
import queue
import time
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from reachy_alive.brain.sensory_cortex.vision.vision_features import SeenFace
from reachy_alive.routes import create_router
from reachy_alive.shared_state import DEFAULT_IDLE_MOVE_INTERVAL_RANGE_S, SharedState

INTERVAL_URL = "/settings/idle-move-interval"
SENSES_URL = "/settings/senses"


@pytest.fixture
def sneezing():
    """A mock standing in for the sneeze move."""
    return MagicMock()


@pytest.fixture
def move_requests():
    """The queue the page puts the moves to play in."""
    return queue.Queue()


@pytest.fixture
def shared_state():
    """A fresh SharedState, shared by the app and the test."""
    return SharedState()


@pytest.fixture
def client(sneezing, move_requests, shared_state):
    """A client for an app serving only the page's routes."""
    app = FastAPI()
    app.include_router(
        create_router({"sneezing": sneezing}, move_requests, shared_state, ["touch", "vision"])
    )
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


def test_every_sense_is_on_at_first(client):
    response = client.get(SENSES_URL)

    assert response.status_code == 200
    assert response.json() == {"touch": True, "vision": True}


def test_a_sense_switched_off_stays_off(client, shared_state):
    response = client.put(f"{SENSES_URL}/touch", json={"enabled": False})

    assert response.status_code == 200
    assert response.json() == {"enabled": False}
    assert shared_state.is_sense_enabled("touch") is False
    assert client.get(SENSES_URL).json() == {"touch": False, "vision": True}


def test_a_sense_switched_back_on_runs_again(client, shared_state):
    client.put(f"{SENSES_URL}/touch", json={"enabled": False})

    client.put(f"{SENSES_URL}/touch", json={"enabled": True})

    assert shared_state.is_sense_enabled("touch") is True


def test_an_unknown_sense_is_404(client):
    response = client.put(f"{SENSES_URL}/smell", json={"enabled": False})

    assert response.status_code == 404
    assert client.get(SENSES_URL).json() == {"touch": True, "vision": True}


def test_a_switch_without_enabled_is_rejected(client, shared_state):
    response = client.put(f"{SENSES_URL}/touch", json={})

    assert response.status_code == 422
    assert shared_state.is_sense_enabled("touch") is True


def test_a_part_of_a_sense_is_switched_like_a_sense(move_requests, shared_state):
    app = FastAPI()
    antennas = ["touch.right", "touch.left"]
    app.include_router(create_router({}, move_requests, shared_state, antennas))
    client = TestClient(app)

    response = client.put(f"{SENSES_URL}/touch.right", json={"enabled": False})

    assert response.status_code == 200
    assert client.get(SENSES_URL).json() == {"touch.right": False, "touch.left": True}


def test_switching_a_sense_from_the_page_is_logged(client, caplog):
    caplog.set_level(logging.INFO)

    client.put(f"{SENSES_URL}/touch", json={"enabled": False})

    assert "touch switched off from the page" in caplog.text


def test_senses_are_all_null_before_anything_happens(client):
    response = client.get("/senses")

    assert response.status_code == 200
    assert response.json() == {
        "inertial": {"last_bump_s_ago": None},
        "touch": {"right_pushed_for_s": None, "left_pushed_for_s": None},
        "hearing": {"last_sudden_noise_s_ago": None},
        "vision": {
            "face_seen_for_s": None,
            "face_distance_m": None,
            "last_face_lost_s_ago": None,
        },
    }


def test_senses_are_sent_as_seconds_before_the_request(client, shared_state):
    three_s_ago = time.monotonic() - 3.0
    shared_state.inertial.record_bump(three_s_ago)
    shared_state.touch.record_antenna_pushed_since("left", three_s_ago)
    shared_state.hearing.record_sudden_noise(three_s_ago)
    shared_state.vision.record_face_appeared(three_s_ago, SeenFace(x=0.0, y=0.0, distance_m=1.2))

    senses = client.get("/senses").json()

    assert senses["inertial"]["last_bump_s_ago"] == pytest.approx(3.0, abs=0.5)
    assert senses["touch"]["left_pushed_for_s"] == pytest.approx(3.0, abs=0.5)
    assert senses["touch"]["right_pushed_for_s"] is None
    assert senses["hearing"]["last_sudden_noise_s_ago"] == pytest.approx(3.0, abs=0.5)
    assert senses["vision"]["face_seen_for_s"] == pytest.approx(3.0, abs=0.5)
    assert senses["vision"]["face_distance_m"] == 1.2


def test_a_lost_face_has_no_distance_and_a_time_since_it_left(client, shared_state):
    shared_state.vision.record_face_appeared(time.monotonic() - 5.0, SeenFace(0.0, 0.0, 1.2))
    shared_state.vision.record_face_lost(time.monotonic() - 2.0)

    vision = client.get("/senses").json()["vision"]

    assert vision["face_seen_for_s"] is None
    assert vision["face_distance_m"] is None
    assert vision["last_face_lost_s_ago"] == pytest.approx(2.0, abs=0.5)

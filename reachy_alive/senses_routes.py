"""A route for the senses page: what the robot perceives right now, as JSON."""

import time

from fastapi import APIRouter

from reachy_alive.shared_state import SharedState


def create_senses_router(shared_state: SharedState) -> APIRouter:
    """Build the route the senses page polls a few times a second."""
    router = APIRouter()

    @router.get("/senses-state")
    def senses_state() -> dict:
        main_face = shared_state.vision.main_face()
        return {
            # The page compares every time below to this one: same clock.
            "now": time.monotonic(),
            "last_bump_at": shared_state.last_bump_at(),
            "last_sudden_noise_at": shared_state.last_sudden_noise_at(),
            "right_antenna_pushed_since": shared_state.antenna_pushed_since("right"),
            "left_antenna_pushed_since": shared_state.antenna_pushed_since("left"),
            "face_seen_since": shared_state.vision.face_seen_since(),
            "last_face_lost_at": shared_state.vision.last_face_lost_at(),
            "face_distance_m": None if main_face is None else main_face.distance_m,
        }

    return router

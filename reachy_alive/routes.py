"""HTTP routes behind the app's page: list and play moves, read and change settings."""

import queue

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from reachy_alive.moves.base import Move
from reachy_alive.shared_state import SharedState

# Below this, the robot barely breathes between idle moves; above, the page
# would look broken.
MIN_IDLE_MOVE_INTERVAL_S = 5.0
MAX_IDLE_MOVE_INTERVAL_S = 600.0


class IdleMoveInterval(BaseModel):
    """Seconds to wait between two idle moves, as the app's page sends them."""

    min_s: float = Field(ge=MIN_IDLE_MOVE_INTERVAL_S, le=MAX_IDLE_MOVE_INTERVAL_S)
    max_s: float = Field(ge=MIN_IDLE_MOVE_INTERVAL_S, le=MAX_IDLE_MOVE_INTERVAL_S)


def create_router(
    moves_by_name: dict[str, Move],
    move_requests: queue.Queue,
    shared_state: SharedState,
) -> APIRouter:
    """Build the routes the app's page calls.

    Args:
        moves_by_name: Every move the page can play, by name.
        move_requests: Where requested moves wait to be played.
        shared_state: Where the settings live.

    Returns:
        A router to include in the app's web server.
    """
    router = APIRouter()

    @router.get("/moves")
    def list_moves() -> list[str]:
        return sorted(moves_by_name)

    @router.post("/moves/{name}/play", status_code=202)
    def request_move(name: str) -> dict[str, str]:
        if name not in moves_by_name:
            raise HTTPException(status_code=404, detail=f"Unknown move: {name}")
        move_requests.put(moves_by_name[name])
        return {"requested": name}

    @router.get("/settings/idle-move-interval")
    def get_idle_move_interval() -> IdleMoveInterval:
        min_s, max_s = shared_state.idle_move_interval_range_s()
        return IdleMoveInterval(min_s=min_s, max_s=max_s)

    @router.put("/settings/idle-move-interval")
    def set_idle_move_interval(interval: IdleMoveInterval) -> IdleMoveInterval:
        if interval.min_s > interval.max_s:
            raise HTTPException(status_code=422, detail="min_s must not exceed max_s")
        shared_state.set_idle_move_interval_range_s(interval.min_s, interval.max_s)
        return interval

    return router
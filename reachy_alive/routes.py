"""HTTP routes behind the app's page: moves, settings, and what the senses perceive."""

import logging
import queue
import time

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from reachy_alive.moves.base import Move
from reachy_alive.shared_state import SharedState

logger = logging.getLogger(__name__)

# Below this, the robot barely breathes between idle moves; above, the page
# would look broken.
MIN_IDLE_MOVE_INTERVAL_S = 5.0
MAX_IDLE_MOVE_INTERVAL_S = 600.0


class IdleMoveInterval(BaseModel):
    """Seconds to wait between two idle moves, as the app's page sends them."""

    min_s: float = Field(ge=MIN_IDLE_MOVE_INTERVAL_S, le=MAX_IDLE_MOVE_INTERVAL_S)
    max_s: float = Field(ge=MIN_IDLE_MOVE_INTERVAL_S, le=MAX_IDLE_MOVE_INTERVAL_S)


class SenseSwitch(BaseModel):
    """Whether a sense runs, as the page's checkbox sends it."""

    enabled: bool


class InertialReport(BaseModel):
    """What the inertial unit felt, in seconds before the request."""

    last_bump_s_ago: float | None


class TouchReport(BaseModel):
    """How long each antenna has been pushed, in seconds, or None if it isn't."""

    right_pushed_for_s: float | None
    left_pushed_for_s: float | None


class HearingReport(BaseModel):
    """What the robot heard, in seconds before the request."""

    last_sudden_noise_s_ago: float | None


class VisionReport(BaseModel):
    """What the robot sees: how long a face has been in view, how far, when one left."""

    face_seen_for_s: float | None
    face_distance_m: float | None
    last_face_lost_s_ago: float | None


class SensesReport(BaseModel):
    """The facts of every sense, as the app's page shows them.

    Facts are dated with time.monotonic(), a clock that means nothing outside
    this process: they are sent as ages, in seconds. None means it never
    happened, or isn't happening now.
    """

    inertial: InertialReport
    touch: TouchReport
    hearing: HearingReport
    vision: VisionReport


def create_router(
    moves_by_name: dict[str, Move],
    move_requests: queue.Queue,
    shared_state: SharedState,
    sense_names: list[str],
) -> APIRouter:
    """Build the routes the app's page calls.

    Args:
        moves_by_name: Every move the page can play, by name.
        move_requests: Where requested moves wait to be played.
        shared_state: Where the settings and the senses' facts live.
        sense_names: The NAME of every sense, which the page can switch off.

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

    @router.get("/settings/senses")
    def get_senses_enabled() -> dict[str, bool]:
        return {name: shared_state.is_sense_enabled(name) for name in sense_names}

    @router.put("/settings/senses/{name}")
    def set_sense_enabled(name: str, switch: SenseSwitch) -> SenseSwitch:
        if name not in sense_names:
            raise HTTPException(status_code=404, detail=f"Unknown sense: {name}")
        shared_state.set_sense_enabled(name, switch.enabled)
        logger.info("%s switched %s from the page", name, "on" if switch.enabled else "off")
        return switch

    @router.get("/senses")
    def get_senses() -> SensesReport:
        now = time.monotonic()  # one reading, so every age is measured from the same instant
        return SensesReport(
            inertial=_inertial_report(shared_state, now),
            touch=_touch_report(shared_state, now),
            hearing=_hearing_report(shared_state, now),
            vision=_vision_report(shared_state, now),
        )

    return router


def _inertial_report(shared_state: SharedState, now: float) -> InertialReport:
    """Read the inertial facts, as ages."""
    return InertialReport(
        last_bump_s_ago=_seconds_since(shared_state.inertial.last_bump_at(), now),
    )


def _touch_report(shared_state: SharedState, now: float) -> TouchReport:
    """Read the touch facts, as ages."""
    touch = shared_state.touch
    return TouchReport(
        right_pushed_for_s=_seconds_since(touch.antenna_pushed_since("right"), now),
        left_pushed_for_s=_seconds_since(touch.antenna_pushed_since("left"), now),
    )


def _hearing_report(shared_state: SharedState, now: float) -> HearingReport:
    """Read the hearing facts, as ages."""
    return HearingReport(
        last_sudden_noise_s_ago=_seconds_since(shared_state.hearing.last_sudden_noise_at(), now),
    )


def _vision_report(shared_state: SharedState, now: float) -> VisionReport:
    """Read the vision facts, as ages, and the distance of the face in view."""
    vision = shared_state.vision
    face = vision.main_face()
    return VisionReport(
        face_seen_for_s=_seconds_since(vision.face_seen_since(), now),
        face_distance_m=None if face is None else face.distance_m,
        last_face_lost_s_ago=_seconds_since(vision.last_face_lost_at(), now),
    )


def _seconds_since(at: float | None, now: float) -> float | None:
    """Turn a time.monotonic() reading into seconds before `now`, keeping None."""
    return None if at is None else now - at

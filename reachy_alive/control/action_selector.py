"""Chooses, each tick, which move the robot plays, and cuts it into ticks."""

import logging
import queue

from reachy_alive.brain.brainstem.breathing import get_breathing_pose
from reachy_alive.brain.brainstem.idle_manager import IdleManager
from reachy_alive.control.commands import RobotCommand
from reachy_alive.moves.base import Move, ReturningToNeutral, SoundCue
from reachy_alive.shared_state import SharedState

logger = logging.getLogger(__name__)


class ActionSelector:
    """Chooses which move the robot plays, and cuts it into one command per tick.

    A move requested from the app's page wins over an idle move. The chosen
    move is cut tick by tick, then its way back to neutral; only then is the
    next proposal heard, and if several requests arrived meanwhile, only the
    latest plays. When nobody proposes a move, the robot breathes.
    """

    def __init__(
        self, idle_manager: IdleManager, move_requests: queue.Queue, shared_state: SharedState
    ) -> None:
        """Keep where proposals come from, and the facts the robot's moves need.

        Args:
            idle_manager: Proposes an idle move now and then.
            move_requests: Moves requested from the app's page.
            shared_state: Read the last pose sent, where each way back to
                neutral starts.
        """
        self._idle_manager = idle_manager
        self._move_requests = move_requests
        self._shared_state = shared_state
        # The move being cut into ticks: None while the robot breathes.
        self._move: Move | None = None
        self._move_started_at_s = 0.0
        self._cues_left: list[SoundCue] = []
        self._returning_to_neutral = False
        # When the current stretch of breathing began; None until the next tick.
        self._breathing_started_at_s: float | None = None

    def decide(self, t: float) -> RobotCommand:
        """Return this tick's command.

        Args:
            t: Elapsed time in seconds since the control loop started.

        Returns:
            The tick of the move being played, otherwise of a move just
            chosen, otherwise of breathing.
        """
        move_is_over = self._move is not None and t - self._move_started_at_s >= self._move.duration
        if move_is_over:
            self._end_move(t)
        if self._move is None:
            self._choose_move_by_priority(t)
        if self._move is None:
            return self._breathing_tick(t)
        return self._move_tick(t)

    def _end_move(self, t: float) -> None:
        """Ease back to neutral from the last pose sent, or stop if that was the way back."""
        if self._returning_to_neutral:
            self._move = None
            return
        last_pose_sent = self._shared_state.last_commanded_pose()
        way_back = ReturningToNeutral(
            (last_pose_sent.head, last_pose_sent.antennas, last_pose_sent.body_yaw)
        )
        self._returning_to_neutral = True
        self._start_cutting(way_back, t)

    def _choose_move_by_priority(self, t: float) -> None:
        """Start the proposal with the highest priority, if any: a request, otherwise idle."""
        move = self._latest_requested_move()
        if move is not None:
            logger.info("Playing %s (requested)", move.name)
        else:
            move = self._idle_manager.propose()
        if move is None:
            return

        move.draw_variations()
        self._returning_to_neutral = False
        self._start_cutting(move, t)
        # Every move ends at neutral, where breathing starts.
        self._breathing_started_at_s = None

    def _start_cutting(self, move: Move, t: float) -> None:
        """Make move the one being cut into ticks, from t."""
        self._move = move
        self._move_started_at_s = t
        self._cues_left = list(move.sound_cues)

    def _latest_requested_move(self) -> Move | None:
        """Empty the request queue and return its latest move, if any."""
        latest = None
        while True:
            try:
                latest = self._move_requests.get_nowait()
            except queue.Empty:
                return latest

    def _breathing_tick(self, t: float) -> RobotCommand:
        """Return this tick of breathing, starting a new stretch after a move."""
        if self._breathing_started_at_s is None:
            self._breathing_started_at_s = t
        head, antennas = get_breathing_pose(t - self._breathing_started_at_s)
        return RobotCommand(head=head, antennas=antennas)

    def _move_tick(self, t: float) -> RobotCommand:
        """Return this tick of the move being played: its pose, and the sounds due by now."""
        elapsed_s = t - self._move_started_at_s
        sounds = []
        while self._cues_left and self._cues_left[0].at_s <= elapsed_s:
            sounds.append(self._cues_left.pop(0).path)

        head, antennas, body_yaw = self._move.evaluate(elapsed_s)
        return RobotCommand(
            head=head, antennas=antennas, body_yaw=body_yaw, sounds=tuple(sounds), from_move=True
        )

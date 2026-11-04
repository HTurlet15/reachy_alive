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

    A move plays to its end, then eases back to neutral. Only then is the
    next move chosen: a move requested from the app's page wins over an idle
    move, and if several requests arrived meanwhile, only the latest plays.
    When there is no move to play, the robot breathes; how long it has been
    breathing is what tells IdleManager whether an idle move is due.
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
        # The move cut into ticks: None while the robot breathes.
        self._current_move: Move | None = None
        self._current_move_started_at_s = 0.0
        self._cues_left: list[SoundCue] = []
        # When the current stretch of breathing began; None until the next tick.
        self._breathing_started_at_s: float | None = None

    def decide(self, t: float) -> RobotCommand:
        """Return this tick's command: the tick of the current move, or of breathing.

        Args:
            t: Elapsed time in seconds since the control loop started.
        """
        self._update_current_move(t)
        if self._current_move is None:
            return self._breathing_tick(t)
        return self._move_tick(t)

    def _update_current_move(self, t: float) -> None:
        """Keep the move playing, or set the next one, highest priority first."""
        current = self._current_move

        # 1. A move is playing: it goes on to its end, until sprint D.
        if current is not None and t - self._current_move_started_at_s < current.duration:
            return

        # 2. A move just ended: ease back to neutral from the last pose sent.
        if current is not None and not isinstance(current, ReturningToNeutral):
            self._set_current_move(self._way_back(), t)
            return

        # 3. A move was requested from the app's page: play the latest one.
        requested = self._latest_requested_move()
        if requested is not None:
            logger.info("Playing %s (requested)", requested.name)
            self._set_current_move(requested, t)
            return

        # 4. The robot has rested long enough: an idle move, otherwise None to breathe.
        idle_move = self._idle_manager.propose(self._resting_for_s(t))
        self._set_current_move(idle_move, t)

    def _way_back(self) -> ReturningToNeutral:
        """Return the way back to neutral from the last pose sent."""
        last_pose_sent = self._shared_state.last_commanded_pose()
        return ReturningToNeutral(
            (last_pose_sent.head, last_pose_sent.antennas, last_pose_sent.body_yaw)
        )

    def _set_current_move(self, move: Move | None, t: float) -> None:
        """Make move the one cut into ticks from t on; None: the robot breathes."""
        self._current_move = move
        self._current_move_started_at_s = t
        if move is None:
            return
        move.draw_variations()
        self._cues_left = list(move.sound_cues)
        # Every move ends at neutral, where breathing starts.
        self._breathing_started_at_s = None

    def _latest_requested_move(self) -> Move | None:
        """Empty the request queue and return its latest move, if any."""
        latest = None
        while True:
            try:
                latest = self._move_requests.get_nowait()
            except queue.Empty:
                return latest

    def _resting_for_s(self, t: float) -> float:
        """Return how long the robot has been breathing: 0 on the tick a move ends."""
        if self._breathing_started_at_s is None:
            return 0.0
        return t - self._breathing_started_at_s

    def _breathing_tick(self, t: float) -> RobotCommand:
        """Return this tick of breathing, starting a new stretch after a move."""
        if self._breathing_started_at_s is None:
            self._breathing_started_at_s = t
        head, antennas = get_breathing_pose(t - self._breathing_started_at_s)
        return RobotCommand(head=head, antennas=antennas)

    def _move_tick(self, t: float) -> RobotCommand:
        """Return this tick of the move playing: its pose, and the sounds due by now."""
        elapsed_s = t - self._current_move_started_at_s
        sounds = []
        while self._cues_left and self._cues_left[0].at_s <= elapsed_s:
            sounds.append(self._cues_left.pop(0).path)

        head, antennas, body_yaw = self._current_move.evaluate(elapsed_s)
        return RobotCommand(
            head=head, antennas=antennas, body_yaw=body_yaw, sounds=tuple(sounds), from_move=True
        )

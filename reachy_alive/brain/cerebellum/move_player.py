"""Plays the move it is given, one pose per tick, and breathes in between."""

from reachy_alive.brain.brainstem.breathing import get_breathing_pose
from reachy_alive.moves.base import Move, ReturningToNeutral, SoundCue
from reachy_alive.shared_state import SharedState
from reachy_alive.spinal_cord.commands import RobotCommand


class MovePlayer:
    """Cuts the move it is given into one command per tick.

    It never chooses. The ActionSelector hands it a move to start on one
    tick only, like pressing play on a remote; the player then keeps what is
    playing, and since when, until it ends. It is the only one to write what
    is playing; the ActionSelector only asks whether it is busy.

    A move plays to its end, then eases back to neutral from the last pose
    sent; until both are over, it is busy. In between, the robot breathes,
    and the player keeps the breathing's clock: how long the robot has been
    resting is what tells the IdleManager when an idle move is due.
    """

    def __init__(self, shared_state: SharedState) -> None:
        """Keep where the way back to neutral starts from.

        Args:
            shared_state: Read the last pose sent, where each way back to
                neutral starts.
        """
        self._shared_state = shared_state
        # What is playing, and since when: None while the robot breathes.
        # Written only in _update_current_move. The start time is read only
        # while a move plays.
        self._current_move: Move | None = None
        self._current_move_started_at = 0.0
        self._cues_left: list[SoundCue] = []
        # When the current stretch of breathing began; None until the next tick.
        self._breathing_started_at: float | None = None

    def tick(self, now: float, move_to_start: Move | None) -> RobotCommand:
        """Return this tick's command: the tick of the current move, or of breathing.

        Args:
            now: This tick's time.monotonic() reading.
            move_to_start: An order for this tick only: the move the
                ActionSelector picked to start now (a requested or an idle
                move). None on most ticks: a move is still playing, or
                nothing was proposed.
        """
        self._update_current_move(now, move_to_start)
        if self._current_move is None:
            return self._breathing_tick(now)
        return self._move_tick(now)

    def _update_current_move(self, now: float, move_to_start: Move | None) -> None:
        """Start the move handed over, or keep the move playing, or move on from it."""
        current = self._current_move

        # 1. A move to start was handed over: it starts now.
        if move_to_start is not None:
            self._set_current_move(move_to_start, now)
            return

        # 2. A move is playing: it goes on to its end, until sprint D.
        if current is not None and now - self._current_move_started_at < current.duration:
            return

        # 3. A move just ended: ease back to neutral from the last pose sent.
        if current is not None and not isinstance(current, ReturningToNeutral):
            self._set_current_move(self._way_back(), now)
            return

        # 4. The way back is over, or nothing was playing: the robot breathes.
        self._current_move = None

    def _way_back(self) -> ReturningToNeutral:
        """Return the way back to neutral from the last pose sent."""
        last_pose_sent = self._shared_state.last_commanded_pose()
        return ReturningToNeutral(
            (last_pose_sent.head, last_pose_sent.antennas, last_pose_sent.body_yaw)
        )

    def _set_current_move(self, move: Move, now: float) -> None:
        """Make move the one cut into ticks from now."""
        self._current_move = move
        self._current_move_started_at = now
        move.draw_variations()
        self._cues_left = list(move.sound_cues)
        # Every move ends at neutral, where breathing starts.
        self._breathing_started_at = None

    def is_busy(self, now: float) -> bool:
        """Return whether a move, or its way back to neutral, is still to play."""
        current = self._current_move
        if current is None:
            return False
        still_playing = now - self._current_move_started_at < current.duration
        return still_playing or not isinstance(current, ReturningToNeutral)

    def resting_for_s(self, now: float) -> float:
        """Return how long the robot has been breathing: 0 on the tick a move ends."""
        if self._breathing_started_at is None:
            return 0.0
        return now - self._breathing_started_at

    def _breathing_tick(self, now: float) -> RobotCommand:
        """Return this tick of breathing, starting a new stretch after a move."""
        if self._breathing_started_at is None:
            self._breathing_started_at = now
        head, antennas = get_breathing_pose(now - self._breathing_started_at)
        return RobotCommand(head=head, antennas=antennas)

    def _move_tick(self, now: float) -> RobotCommand:
        """Return this tick of the move playing: its pose, and the sounds due by now."""
        elapsed_s = now - self._current_move_started_at
        sounds = []
        while self._cues_left and self._cues_left[0].at_s <= elapsed_s:
            sounds.append(self._cues_left.pop(0).path)

        head, antennas, body_yaw = self._current_move.evaluate(elapsed_s)
        return RobotCommand(
            head=head, antennas=antennas, body_yaw=body_yaw, sounds=tuple(sounds), from_move=True
        )

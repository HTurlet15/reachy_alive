"""What a decision-maker proposes to the ActionSelector, for one tick."""

from dataclasses import dataclass

from reachy_alive.moves.base import Move


@dataclass(frozen=True)
class Proposal:
    """What a decision-maker wants the robot to do: orders for one tick.

    Every decision-maker returns one, in the same shape: the ActionSelector
    compares them by priority, and hands the one it chooses to the
    MovePlayer, unchanged. An order, not a fact: it is used once, on the
    tick it is chosen, and never stored in SharedState.

    Attributes:
        source: Who proposes it: "page", "idle", or "try-move" today.
        move_to_start: The move to start now, or None.
    """

    source: str
    move_to_start: Move | None = None

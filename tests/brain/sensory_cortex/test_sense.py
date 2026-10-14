"""Unit tests for Sense, the contract every sense follows."""

from dataclasses import dataclass
from unittest.mock import MagicMock

from reachy_alive.brain.sensory_cortex.sense import Sense
from reachy_alive.shared_state import SharedState


@dataclass(frozen=True)
class MadeUpFeatures:
    """The least features a sense can give."""

    t: float
    robot_moving_itself: bool


class MinimalSense(Sense):
    """A sense that writes only what it must: _perceive."""

    def __init__(self, shared_state: SharedState, gives_nothing: bool = False) -> None:
        super().__init__(MagicMock(), shared_state)
        self.gives_nothing = gives_nothing

    def _perceive(self, t: float, robot_moving_itself: bool) -> MadeUpFeatures | None:
        if self.gives_nothing:
            return None
        return MadeUpFeatures(t=t, robot_moving_itself=robot_moving_itself)


def test_a_sense_is_available_and_reads_as_fast_as_it_can_by_default():
    sense = MinimalSense(SharedState())

    assert sense.is_available() is True
    assert sense.PERIOD_S == 0.0


def test_opening_and_closing_do_nothing_by_default():
    sense = MinimalSense(SharedState())

    sense.open()
    sense.close()

    assert sense.read_once(1.0) is not None


def test_a_reading_gives_the_features_dated_by_the_reading():
    features = MinimalSense(SharedState()).read_once(12.0)

    assert features == MadeUpFeatures(t=12.0, robot_moving_itself=False)


def test_no_features_when_the_sensor_gave_nothing():
    assert MinimalSense(SharedState(), gives_nothing=True).read_once(0.0) is None


def test_the_features_say_when_a_move_plays():
    state = SharedState()
    state.set_move_playing(True)

    assert MinimalSense(state).read_once(0.0).robot_moving_itself is True


def test_the_robot_still_moves_itself_until_it_settles():
    state = SharedState()
    sense = MinimalSense(state)
    state.set_move_playing(True)
    state.set_move_playing(False)
    ended_at = state.last_move_ended_at()

    assert sense.read_once(ended_at + 0.3).robot_moving_itself is True  # within SETTLE_AFTER_MOVE_S
    assert sense.read_once(ended_at + 0.6).robot_moving_itself is False
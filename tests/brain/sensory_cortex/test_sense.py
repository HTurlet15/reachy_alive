"""Unit tests for Sense, the contract every sense follows."""

import pytest

from reachy_alive.brain.sensory_cortex.sense import Sense


class MinimalSense(Sense):
    """A sense that writes only what it must: read_once."""

    def read_once(self, now: float):
        return now


def test_a_sense_is_available_and_reads_as_fast_as_it_can_by_default():
    sense = MinimalSense()

    assert sense.is_available() is True
    assert sense.PERIOD_S == 0.0


def test_opening_and_closing_do_nothing_by_default():
    sense = MinimalSense()

    sense.open()
    sense.close()

    assert sense.read_once(1.0) == 1.0


def test_a_sense_without_read_once_cannot_be_built():
    class ForgetfulSense(Sense):
        pass

    with pytest.raises(TypeError):
        ForgetfulSense()

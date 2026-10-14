"""Detector: the contract every detector follows, so that SenseManager can feed any of them."""

from abc import ABC, abstractmethod


class Detector(ABC):
    """Reads the features of one sense, and records what they mean as facts.

    SenseManager builds it with its sense's facts, and hands it the features
    of every reading. To write a detector, write _detect: this class hands it
    the features of the readings the robot didn't disturb. The others go to
    _while_robot_moves, which ignores them unless overridden.
    """

    def __init__(self, facts) -> None:
        """Keep where the detector records its facts.

        Args:
            facts: Its sense's facts in SharedState, such as `shared_state.vision`.
        """
        self._facts = facts

    def update(self, features) -> None:
        """Read the features of one reading of the sense."""
        if features.robot_moving_itself:
            self._while_robot_moves(features)
        else:
            self._detect(features)

    @abstractmethod
    def _detect(self, features) -> None:
        """Read the features of an undisturbed reading, and record the facts they show."""

    def _while_robot_moves(self, features) -> None:
        """Read the features of a reading the robot disturbed. Ignores them by default.

        Override it when the detector must keep following its sensor even
        then, without recording facts: a background level, for example.
        """
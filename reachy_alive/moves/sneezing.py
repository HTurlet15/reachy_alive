"""Mixed sneeze gesture: the head comes from a Marionette recording, the
antennas are coded on top -- they climb with each inhale, then drop on the
sneeze.

This is the reference mixed move. See moves/README.md for how to write one.
"""

import random

import numpy as np
from reachy_mini import ReachyMini
from reachy_mini.motion.recorded_move import RecordedMoves

from reachy_alive.interpolate import interpolate
from reachy_alive.moves.base import NEUTRAL_ANTENNAS_RAD, Move, PhasedMove


class Sneezing(PhasedMove):
    """Plays a sneeze: three building inhales, the sneeze, then relief."""

    SOUNDS_DIR = Move.SOUNDS_DIR / "sneezing"
    RECORDING_NAME = "sneezing"

    PHASE_SOUNDS = {
        "inhale1": "inhale1.wav",
        "inhale2": "inhale2.wav",
        "inhale3": "inhale3.wav",
        "sneeze": "sneeze.wav",
        "relief": "relief.wav",
    }
    # Must match assets/sounds/sneezing/compose.py: the head was recorded
    # against the file it composes.
    PHASE_PADDING_S = {
        "inhale1": 0.5,
        "inhale2": 0.5,
        "inhale3": 0.5,
        "sneeze": 0.5,
    }

    INHALE_PHASES = ("inhale1", "inhale2", "inhale3")

    # Both antennas move together, mirrored: one value drives the pair.
    ANTENNA_START_RAD = NEUTRAL_ANTENNAS_RAD[0]

    # Inhales: the antennas climb one step per inhale while shaking, then
    # relax a little during the silence that follows.
    RISE_PER_INHALE_RAD = np.deg2rad(5.0)
    RELAX_IN_SILENCE_RAD = np.deg2rad(2.0)
    INHALE_SHAKE_AMPLITUDE_RAD = np.deg2rad(5.0)

    # Sneeze: the antennas drop at once, a little differently each play.
    ANTENNA_SNEEZE_RAD = np.deg2rad(-60.0)
    SNEEZE_ANGLE_VARIATION_RAD = np.deg2rad(10.0)
    SNEEZE_DROP_DURATION_S = 0.06  # about 3 ticks at 50 Hz

    def __init__(self, library: RecordedMoves, tick_hz: float = 50.0) -> None:
        """Load the head recording.

        Args:
            library: Recorded-moves library holding the head recording.
            tick_hz: Frequency, in Hz, at which the pose is updated.
        """
        super().__init__(tick_hz)
        self._recording = library.get(self.RECORDING_NAME)

        # Where, in each inhale's progress p, its sound ends and its
        # silence begins.
        self._silence_start_p = {
            phase: 1.0 - self.PHASE_PADDING_S[phase] / self._phase_duration(phase)
            for phase in self.INHALE_PHASES
        }

        self._sneeze_angle_rad = self.ANTENNA_SNEEZE_RAD

    def _perform(self, reachy_mini: ReachyMini) -> None:
        """Draw this play's sneeze angle, then run the gesture."""
        variation = random.uniform(
            -self.SNEEZE_ANGLE_VARIATION_RAD, self.SNEEZE_ANGLE_VARIATION_RAD
        )
        self._sneeze_angle_rad = self.ANTENNA_SNEEZE_RAD + variation
        super()._perform(reachy_mini)

    def _pose_at(
        self, phase: str, p: float, step: int, elapsed_s: float
    ) -> tuple[np.ndarray, list[float], float]:
        # The phases and the recording last the same, give or take float
        # rounding; don't evaluate past the recording's end.
        t = min(elapsed_s, self._recording.duration)
        head, _, body_yaw = self._recording.evaluate(t)

        if phase in self.INHALE_PHASES:
            antenna = self._inhale_antenna(phase, p, step)
        elif phase == "sneeze":
            antenna = self._sneeze_antenna(elapsed_s)
        else:
            antenna = self._relief_antenna(p)

        return head, [antenna, -antenna], body_yaw

    def _inhale_antenna(self, phase: str, p: float, step: int) -> float:
        """Climb one step while shaking, then relax in the silence. p: 0 -> 1."""
        index = self.INHALE_PHASES.index(phase)
        top = self.ANTENNA_START_RAD + (index + 1) * self.RISE_PER_INHALE_RAD
        silence_start_p = self._silence_start_p[phase]

        if p < silence_start_p:
            if index == 0:
                start = self.ANTENNA_START_RAD
            else:
                start = top - self.RISE_PER_INHALE_RAD - self.RELAX_IN_SILENCE_RAD
            climb = interpolate(start, top, p / silence_start_p)
            shake_sign = 1 if step % 2 == 0 else -1
            return climb + shake_sign * self.INHALE_SHAKE_AMPLITUDE_RAD

        relax = (p - silence_start_p) / (1.0 - silence_start_p)
        return interpolate(top, top - self.RELAX_IN_SILENCE_RAD, relax)

    def _sneeze_antenna(self, elapsed_s: float) -> float:
        """Drop at once to this play's sneeze angle, then hold."""
        since_sneeze_s = elapsed_s - self.phase_ends_s["inhale3"]
        drop = min(since_sneeze_s / self.SNEEZE_DROP_DURATION_S, 1.0)
        last_inhale_end = (
            self.ANTENNA_START_RAD
            + len(self.INHALE_PHASES) * self.RISE_PER_INHALE_RAD
            - self.RELAX_IN_SILENCE_RAD
        )
        return interpolate(last_inhale_end, self._sneeze_angle_rad, drop)

    def _relief_antenna(self, p: float) -> float:
        """Rise slowly from the sneeze angle back to the start. p: 0 -> 1."""
        return interpolate(self._sneeze_angle_rad, self.ANTENNA_START_RAD, p)
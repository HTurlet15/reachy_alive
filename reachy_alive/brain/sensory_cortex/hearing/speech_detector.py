"""Speech: someone speaking near the robot, from how much the sound sounds like a voice."""

import logging

from reachy_alive.brain.sensory_cortex.detector import Detector
from reachy_alive.brain.sensory_cortex.hearing.hearing_features import HearingFeatures
from reachy_alive.shared_state import HearingFacts

logger = logging.getLogger(__name__)


class SpeechDetector(Detector):
    """Turns the voice probability into speech that starts and ends: Silero's own recipe.

    Speech starts on the first frame where the voice is clear. It ends once
    the voice has been gone for a while: a short dip between words doesn't
    end it. Silero's VADIterator does the same (silero-vad 6.3),
    with its thresholds; the time to end is ours.
    """

    # At or above this, the voice is clear: speech starts, or goes on.
    START_PROBABILITY = 0.5
    # Under this, the voice is gone. In between, the voice is unsure: it
    # neither starts speech, nor ends it, nor brings it back.
    END_PROBABILITY = 0.35
    # How long the voice must stay gone for speech to end. Silero's default
    # is 0.1 s. Measured on recordings of someone talking with the app
    # running: 0.3 s cut continuous talk into 29 pieces, 0.1 s into 39.
    # Provisional: to check on the robot.
    END_AFTER_S = 0.3

    def __init__(self, facts: HearingFacts) -> None:
        """Start hearing nobody."""
        super().__init__(facts)
        self.forget()

    def forget(self) -> None:
        """Forget the speech going on: the sense can no longer tell whether someone speaks."""
        self._speaking = False
        # While speaking: the frame where the voice went, until it comes back.
        self._frame_voice_gone: HearingFeatures | None = None
        self._facts.record_speaking_since(None)

    def _detect(self, features: HearingFeatures) -> None:
        """Follow the voice probability through one frame, and record speech that starts or ends."""
        if self._speaking:
            self._follow_speech(features)
        else:
            self._wait_for_speech(features)

    def _wait_for_speech(self, features: HearingFeatures) -> None:
        """Start speech on the first frame where the voice is clear."""
        voice_clear = features.voice_probability >= self.START_PROBABILITY
        if voice_clear:
            self._speaking = True
            self._facts.record_speaking_since(features.perceived_at)
            logger.info("Someone is speaking")

    def _follow_speech(self, features: HearingFeatures) -> None:
        """End speech once the voice has been gone for END_AFTER_S."""
        voice_clear = features.voice_probability >= self.START_PROBABILITY
        voice_gone = features.voice_probability < self.END_PROBABILITY

        # 1. The voice is clear: speech goes on, even after a short dip.
        if voice_clear:
            self._frame_voice_gone = None
            return

        # 2. The voice just went: remember the frame, and wait.
        if voice_gone and self._frame_voice_gone is None:
            self._frame_voice_gone = features

        # 3. The voice has been gone long enough: speech ended when it went.
        if self._frame_voice_gone is None:
            return  # neither clear nor gone, and it never went: still speaking
        gone_for_s = features.time_listened_s - self._frame_voice_gone.time_listened_s
        if gone_for_s >= self.END_AFTER_S:
            self._facts.record_speech_ended(self._frame_voice_gone.perceived_at)
            self._speaking = False
            self._frame_voice_gone = None
            logger.info("Speech ended")

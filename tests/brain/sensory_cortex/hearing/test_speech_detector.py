"""Unit tests for SpeechDetector: the voice probability becomes speech that starts and ends."""

from reachy_alive.brain.sensory_cortex.hearing.hearing_features import HearingFeatures
from reachy_alive.brain.sensory_cortex.hearing.speech_detector import SpeechDetector
from reachy_alive.shared_state import HearingFacts

FRAME_S = 0.02
START = 100.0  # perceived_at of the first frame, on time.monotonic()'s clock
VOICE = 0.9
SILENCE = 0.02


def at(probability, seconds):
    """The voice probability of each frame, held for `seconds`."""
    return [probability] * round(seconds / FRAME_S)


def heard(probabilities):
    """Feed one frame per probability, 20 ms apart, to a new detector, and return its facts."""
    facts = HearingFacts()
    detector = SpeechDetector(facts)
    for i, probability in enumerate(probabilities):
        detector.update(
            HearingFeatures(
                perceived_at=START + i * FRAME_S,
                time_listened_s=i * FRAME_S,
                level_dbfs=-40.0,
                robot_moving_itself=False,
                voice_probability=probability,
            )
        )
    return facts


def test_speech_starts_on_the_first_frame_that_sounds_like_a_voice():
    facts = heard(at(SILENCE, 1.0) + at(VOICE, 0.1))

    assert facts.speaking_since() == START + 1.0


def test_an_unsure_voice_does_not_start_speech():
    facts = heard(at(SILENCE, 1.0) + at(0.45, 2.0))

    assert facts.speaking_since() is None


def test_a_dip_between_words_does_not_end_speech():
    facts = heard(at(VOICE, 1.0) + at(0.1, 0.2) + at(VOICE, 1.0))

    assert facts.speaking_since() == START
    assert facts.last_speech_ended_at() is None


def test_speech_ends_once_the_voice_has_been_gone_for_end_after_s_dated_when_it_went():
    facts = heard(at(VOICE, 1.0) + at(SILENCE, 0.5))

    assert facts.speaking_since() is None
    assert facts.last_speech_ended_at() == START + 1.0


def test_an_unsure_voice_does_not_bring_speech_back():
    # As in Silero's VADIterator: only a clear voice does.
    facts = heard(at(VOICE, 1.0) + at(SILENCE, 0.1) + at(0.45, 0.4))

    assert facts.last_speech_ended_at() == START + 1.0


def test_an_unsure_voice_does_not_end_speech_either():
    facts = heard(at(VOICE, 1.0) + at(0.45, 1.0))

    assert facts.speaking_since() == START
    assert facts.last_speech_ended_at() is None


def test_minutes_of_talking_stay_one_speech():
    # On the robot, speech once ended in the middle of a sentence: never again.
    words_and_dips = (at(VOICE, 0.4) + at(0.2, 0.1)) * 240  # 2 minutes

    facts = heard(words_and_dips)

    assert facts.speaking_since() == START
    assert facts.last_speech_ended_at() is None


def test_speech_can_start_again_after_it_ended():
    facts = heard(at(VOICE, 1.0) + at(SILENCE, 1.0) + at(VOICE, 0.1))

    assert facts.speaking_since() == START + 2.0
    assert facts.last_speech_ended_at() == START + 1.0


def test_forgetting_clears_the_speech_going_on():
    facts = HearingFacts()
    detector = SpeechDetector(facts)
    detector.update(
        HearingFeatures(
            perceived_at=START,
            time_listened_s=0.02,
            level_dbfs=-40.0,
            robot_moving_itself=False,
            voice_probability=VOICE,
        )
    )

    detector.forget()

    assert facts.speaking_since() is None

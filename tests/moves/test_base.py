"""Unit tests for Move, PhasedMove and LibraryMove."""

from pathlib import Path
from unittest.mock import MagicMock

import numpy as np
import pytest
import soundfile as sf

from reachy_alive.moves.base import (
    NEUTRAL_ANTENNAS_RAD,
    NEUTRAL_BODY_YAW_RAD,
    LibraryMove,
    Move,
    PhasedMove,
    ReturningToNeutral,
    SoundCue,
    alternating_sign,
    interpolate,
)
from reachy_alive.moves.robot_sounds import upload_sounds

# --- Move ---------------------------------------------------------------


class _SoundMove(Move):
    """Minimal move: holds still for a few ticks, with one sound at the start."""

    duration = 0.05

    def __init__(self, path: Path) -> None:
        self.sound_cues = (SoundCue(at_s=0.0, path=path),)

    def evaluate(self, t):
        return np.eye(4), [0.0, 0.0], 0.0


SNEEZE = Path("/local/sneeze.wav")


def test_each_sound_plays_from_where_the_robot_finds_it(play, fake_reachy_mini):
    fake_reachy_mini.media.audio.upload_sound.return_value = "/robot/sneeze.wav"

    play(_SoundMove(SNEEZE))

    fake_reachy_mini.media.play_sound.assert_called_once_with("/robot/sneeze.wav")


def test_a_move_uploads_nothing_while_it_plays(play, fake_reachy_mini):
    play(_SoundMove(SNEEZE))

    # The only upload is the app's, before the move: one per sound.
    assert fake_reachy_mini.media.audio.upload_sound.call_count == 1


def test_every_move_ends_with_its_way_back_to_neutral(play, fake_reachy_mini):
    commands = play(_SoundMove(SNEEZE))

    last = commands[-1]
    np.testing.assert_allclose(last.head, np.eye(4), atol=1e-3)
    np.testing.assert_allclose(last.antennas, NEUTRAL_ANTENNAS_RAD, atol=1e-3)
    assert last.body_yaw == pytest.approx(NEUTRAL_BODY_YAW_RAD, abs=1e-3)
    fake_reachy_mini.goto_target.assert_not_called()


def test_the_way_back_starts_from_the_last_pose_sent(play):
    class _TurnedAway(_SoundMove):
        def evaluate(self, t):
            return np.eye(4), [0.5, -0.5], 0.3 + t  # never the same pose twice

    commands = play(_TurnedAway(SNEEZE))

    yaws = [command.body_yaw for command in commands]
    last_of_move = max(range(len(yaws)), key=lambda i: yaws[i])  # the yaw only grows
    first_of_return = commands[last_of_move + 1]
    assert first_of_return.body_yaw == pytest.approx(yaws[last_of_move], abs=1e-3)
    np.testing.assert_allclose(first_of_return.antennas, [0.5, -0.5], atol=1e-3)


def test_name_joins_class_name_words_with_hyphens():
    class DeepBreath(Move):
        duration = 0.0

        def evaluate(self, t):
            return np.eye(4), [0.0, 0.0], 0.0

    assert DeepBreath().name == "deep-breath"


def test_interpolate_goes_from_start_to_end():
    assert interpolate(2.0, 6.0, 0.0) == 2.0
    assert interpolate(2.0, 6.0, 0.5) == 4.0
    assert interpolate(2.0, 6.0, 1.0) == 6.0


# --- alternating_sign ---------------------------------------------------


@pytest.mark.parametrize(
    "elapsed_s, expected_sign",
    [
        (0.00, 1),
        (0.05, 1),  # still in the first half period
        (0.15, -1),  # second half period
        (0.25, 1),  # third: back to the first side
    ],
)
def test_alternating_sign_switches_every_half_period(elapsed_s, expected_sign):
    assert alternating_sign(elapsed_s, half_period_s=0.1) == expected_sign


# --- PhasedMove ---------------------------------------------------------


@pytest.fixture
def sounds_dir(tmp_path):
    """Two short silent sounds: a.wav lasts 0.1 s, b.wav 0.2 s."""
    for name, duration_s in [("a.wav", 0.1), ("b.wav", 0.2)]:
        sf.write(str(tmp_path / name), np.zeros(int(8000 * duration_s)), 8000)
    return tmp_path


def _phased_move_class(sounds_dir, **attributes):
    """Build a PhasedMove subclass: a (0.1 s + 0.05 s), hold (0.3 s), b (0.2 s)."""
    defaults = {
        "SOUNDS_DIR": sounds_dir,
        "PHASE_SOUNDS": {"a": "a.wav", "hold": None, "b": "b.wav"},
        "SILENT_PHASE_DURATIONS_S": {"hold": 0.3},
        "PHASE_PADDING_S": {"a": 0.05},
    }

    def _pose_at(self, phase, p, elapsed_s):
        self.calls.append((phase, p, elapsed_s))
        return np.eye(4), [0.0, 0.0], 0.25

    attributes = {**defaults, **attributes, "_pose_at": _pose_at}
    cls = type("_TestMove", (PhasedMove,), attributes)
    cls.calls = []
    return cls


def test_phase_durations_come_from_sounds_padding_and_silent_phases(sounds_dir):
    move = _phased_move_class(sounds_dir)()

    assert move.phase_ends_s == pytest.approx({"a": 0.15, "hold": 0.45, "b": 0.65})
    assert move.duration == pytest.approx(0.65)


def test_each_sound_is_cued_when_its_phase_begins(sounds_dir):
    move = _phased_move_class(sounds_dir)()

    assert move.sound_cues == (
        SoundCue(at_s=0.0, path=sounds_dir / "a.wav"),
        SoundCue(at_s=pytest.approx(0.45), path=sounds_dir / "b.wav"),  # after hold
    )


def test_evaluate_answers_the_pose_of_the_running_phase(sounds_dir):
    move = _phased_move_class(sounds_dir)()

    head, antennas, body_yaw = move.evaluate(0.3)

    assert move.calls[-1] == ("hold", pytest.approx(0.5), 0.3)  # 0.15 s into 0.3 s
    np.testing.assert_allclose(head, np.eye(4))
    assert body_yaw == 0.25


@pytest.mark.parametrize(
    "elapsed_s, expected_phase, expected_p",
    [
        (0.0, "a", 0.0),
        (0.3, "hold", 0.5),  # 0.15 s into a 0.3 s phase
        (0.55, "b", 0.5),
        (0.66, "b", 1.0),  # overshoot by a fraction of a tick
    ],
)
def test_phase_at_returns_the_phase_and_progress_within_it(
    sounds_dir, elapsed_s, expected_phase, expected_p
):
    move = _phased_move_class(sounds_dir)()

    phase, p = move._phase_at(elapsed_s)

    assert phase == expected_phase
    assert p == pytest.approx(expected_p)


@pytest.mark.parametrize(
    "attributes, error",
    [
        ({"PHASE_SOUNDS": {}}, ValueError),
        ({"SILENT_PHASE_DURATIONS_S": {}}, ValueError),
        ({"PHASE_PADDING_S": {"typo": 0.5}}, ValueError),
        ({"PHASE_SOUNDS": {"a": "missing.wav"}}, FileNotFoundError),
    ],
    ids=["no-phases", "silent-phase-without-duration", "padding-on-unknown-phase", "missing-sound"],
)
def test_invalid_declarations_fail_at_construction(sounds_dir, attributes, error):
    with pytest.raises(error):
        _phased_move_class(sounds_dir, **attributes)()


def test_each_sound_plays_once_and_every_pose_comes_whole(play, fake_reachy_mini, sounds_dir):
    move = _phased_move_class(sounds_dir)()

    commands = play(move)

    assert fake_reachy_mini.media.play_sound.call_count == 2  # a and b; hold is silent
    poses_of_the_move = commands[: len(move.calls)]  # the way back to neutral follows them
    assert poses_of_the_move
    assert all(command.body_yaw == 0.25 for command in poses_of_the_move)


def test_elapsed_s_runs_through_the_move_while_p_restarts_each_phase(play, sounds_dir):
    move = _phased_move_class(sounds_dir)()

    play(move)

    elapsed = [elapsed_s for _, _, elapsed_s in move.calls]
    assert elapsed == sorted(elapsed)
    first_p_of_each_phase = {}
    for phase, p, _ in move.calls:
        first_p_of_each_phase.setdefault(phase, p)
    assert all(p < 0.2 for p in first_p_of_each_phase.values())


def test_variations_are_drawn_once_per_play_before_the_first_pose(play, sounds_dir):
    # Each entry: how many poses had been computed when the draw happened.
    poses_before_each_draw = []

    def draw_variations(self):
        poses_before_each_draw.append(len(self.calls))

    move = _phased_move_class(sounds_dir, draw_variations=draw_variations)()

    play(move)
    poses_in_first_play = len(move.calls)
    play(move)

    assert poses_before_each_draw == [0, poses_in_first_play]


# --- LibraryMove --------------------------------------------------------


@pytest.fixture
def recording():
    """A one-second recording with a sound, as the SDK's library returns it."""
    recording = MagicMock()
    recording.duration = 1.0
    recording.sound_path = Path("/cache/hiccup-full.wav")
    recording.evaluate.return_value = (np.eye(4), np.zeros(2), 0.0)
    return recording


def test_library_move_lasts_as_long_as_its_recording(recording):
    library = MagicMock()
    library.get.return_value = recording

    move = LibraryMove("hiccup-full", library)

    library.get.assert_called_once_with("hiccup-full")
    assert move.duration == 1.0


def test_library_move_cues_the_recording_sound_at_its_start(recording):
    library = MagicMock()
    library.get.return_value = recording

    move = LibraryMove("hiccup-full", library)

    assert move.sound_cues == (SoundCue(at_s=0.0, path=recording.sound_path),)


def test_library_move_without_sound_cues_nothing(recording):
    recording.sound_path = None
    library = MagicMock()
    library.get.return_value = recording

    assert LibraryMove("hiccup-full", library).sound_cues == ()


def test_a_library_move_sound_is_uploaded_like_any_other(fake_reachy_mini, recording):
    library = MagicMock()
    library.get.return_value = recording

    upload_sounds([LibraryMove("hiccup-full", library)], fake_reachy_mini)

    fake_reachy_mini.media.audio.upload_sound.assert_called_once_with("/cache/hiccup-full.wav")


def test_library_move_never_reads_the_recording_at_its_last_frame(recording):
    library = MagicMock()
    library.get.return_value = recording

    LibraryMove("hiccup-full", library).evaluate(1.0)

    (t,), _ = recording.evaluate.call_args
    assert t < 1.0


def test_library_move_plays_through_our_loop_not_the_sdk(play, fake_reachy_mini, recording):
    recording.duration = 0.05
    library = MagicMock()
    library.get.return_value = recording

    play(LibraryMove("hiccup-full", library))

    fake_reachy_mini.play_move.assert_not_called()
    assert fake_reachy_mini.set_target.called
    fake_reachy_mini.media.play_sound.assert_called_once()


# --- ReturningToNeutral -------------------------------------------------


def test_returning_to_neutral_goes_from_its_start_to_neutral():
    from_pose = (np.eye(4), [0.6, -0.6], 0.4)
    move = ReturningToNeutral(from_pose)

    head, antennas, body_yaw = move.evaluate(0.0)
    np.testing.assert_allclose(antennas, [0.6, -0.6])
    assert body_yaw == pytest.approx(0.4)

    head, antennas, body_yaw = move.evaluate(move.duration)
    np.testing.assert_allclose(head, np.eye(4), atol=1e-9)
    np.testing.assert_allclose(antennas, NEUTRAL_ANTENNAS_RAD)
    assert body_yaw == pytest.approx(NEUTRAL_BODY_YAW_RAD)


def test_returning_to_neutral_lasts_half_a_second_and_is_silent():
    move = ReturningToNeutral((np.eye(4), [0.0, 0.0], 0.0))

    assert move.duration == 0.5
    assert move.sound_cues == ()

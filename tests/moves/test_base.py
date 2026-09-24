# tests/moves/test_base.py
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
)

# --- Move ---------------------------------------------------------------


class _SoundMove(Move):
    """Minimal move that plays one sound."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def sound_paths(self) -> list[Path]:
        return [self.path]

    def _perform(self, reachy_mini) -> None:
        self.play_sound(reachy_mini, self.path)


def test_play_plays_the_uploaded_copy_of_a_sound(fake_reachy_mini):
    path = Path("/local/sneeze.wav")
    fake_reachy_mini.media.audio.upload_sound.return_value = "/robot/sneeze.wav"

    _SoundMove(path).play(fake_reachy_mini)

    fake_reachy_mini.media.audio.upload_sound.assert_called_once_with(str(path))
    fake_reachy_mini.media.play_sound.assert_called_once_with("/robot/sneeze.wav")


def test_play_uploads_again_on_every_play(fake_reachy_mini):
    # Another move may have overwritten a file with the same name on the robot.
    move = _SoundMove(Path("/local/exhale.wav"))

    move.play(fake_reachy_mini)
    move.play(fake_reachy_mini)

    assert fake_reachy_mini.media.audio.upload_sound.call_count == 2


def test_local_backend_plays_the_local_file(fake_reachy_mini):
    path = Path("/local/sneeze.wav")
    fake_reachy_mini.media.audio = object()  # no upload_sound: simulation, Lite

    _SoundMove(path).play(fake_reachy_mini)

    fake_reachy_mini.media.play_sound.assert_called_once_with(str(path))


def test_play_sound_rejects_a_sound_missing_from_sound_paths(fake_reachy_mini):
    move = _SoundMove(Path("/local/sneeze.wav"))
    move.prepare(fake_reachy_mini)

    with pytest.raises(KeyError, match="not listed in sound_paths"):
        move.play_sound(fake_reachy_mini, Path("/local/other.wav"))


def test_play_returns_head_antennas_and_body_to_neutral(fake_reachy_mini):
    _SoundMove(Path("/local/sneeze.wav")).play(fake_reachy_mini)

    kwargs = fake_reachy_mini.goto_target.call_args.kwargs
    np.testing.assert_allclose(kwargs["head"], np.eye(4))
    assert kwargs["antennas"] == NEUTRAL_ANTENNAS_RAD
    assert kwargs["body_yaw"] == NEUTRAL_BODY_YAW_RAD


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

    def _pose_at(self, phase, p, step, elapsed_s):
        self.calls.append((phase, p, elapsed_s))
        return np.eye(4), [0.0, 0.0], 0.25

    attributes = {**defaults, **attributes, "_pose_at": _pose_at}
    cls = type("_TestMove", (PhasedMove,), attributes)
    cls.calls = []
    return cls


def test_phase_durations_come_from_sounds_padding_and_silent_phases(sounds_dir):
    move = _phased_move_class(sounds_dir)()

    assert move.phase_ends_s == pytest.approx({"a": 0.15, "hold": 0.45, "b": 0.65})
    assert move.duration_s == pytest.approx(0.65)


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


def test_perform_fires_each_sound_once_and_streams_the_full_pose(fake_reachy_mini, sounds_dir):
    move = _phased_move_class(sounds_dir)()

    move.play(fake_reachy_mini)

    assert fake_reachy_mini.media.play_sound.call_count == 2  # a and b; hold is silent
    assert fake_reachy_mini.set_target.called
    for call in fake_reachy_mini.set_target.call_args_list:
        assert call.kwargs["body_yaw"] == 0.25


def test_elapsed_s_runs_through_the_gesture_while_p_restarts_each_phase(
    fake_reachy_mini, sounds_dir
):
    move = _phased_move_class(sounds_dir)()

    move.play(fake_reachy_mini)

    elapsed = [elapsed_s for _, _, elapsed_s in move.calls]
    assert elapsed == sorted(elapsed)
    first_p_of_each_phase = {}
    for phase, p, _ in move.calls:
        first_p_of_each_phase.setdefault(phase, p)
    assert all(p < 0.2 for p in first_p_of_each_phase.values())


# --- LibraryMove --------------------------------------------------------


def test_library_move_plays_the_recording_with_its_own_sound(fake_reachy_mini):
    library = MagicMock()

    LibraryMove("hiccup-full", library).play(fake_reachy_mini)

    library.get.assert_called_once_with("hiccup-full")
    fake_reachy_mini.play_move.assert_called_once_with(library.get.return_value, sound=True)
    fake_reachy_mini.media.audio.upload_sound.assert_not_called()
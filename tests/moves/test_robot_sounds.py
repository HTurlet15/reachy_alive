"""Unit tests for upload_sounds, with a fake robot."""

import logging
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from reachy_alive.moves.base import SoundCue
from reachy_alive.moves.robot_sounds import upload_sounds


def move_with_sounds(*paths, name="sneezing"):
    """A move whose only trait that matters here: the sounds it starts."""
    move = MagicMock()
    move.name = name
    move.sound_cues = tuple(SoundCue(at_s=0.0, path=Path(path)) for path in paths)
    return move


def test_from_a_laptop_each_sound_is_uploaded_once_and_played_from_its_copy(fake_reachy_mini):
    fake_reachy_mini.media.audio.upload_sound.side_effect = lambda path: "/robot/" + Path(path).name
    moves = [move_with_sounds("/local/inhale1.wav", "/local/sneeze.wav"), move_with_sounds()]

    robot_sounds = upload_sounds(moves, fake_reachy_mini)

    assert robot_sounds == {
        Path("/local/inhale1.wav"): "/robot/inhale1.wav",
        Path("/local/sneeze.wav"): "/robot/sneeze.wav",
    }
    assert fake_reachy_mini.media.audio.upload_sound.call_count == 2


def test_on_the_robot_each_sound_plays_from_its_own_file(fake_reachy_mini):
    fake_reachy_mini.media.audio = object()  # no upload_sound: the local backend

    robot_sounds = upload_sounds([move_with_sounds("/local/sneeze.wav")], fake_reachy_mini)

    assert robot_sounds == {Path("/local/sneeze.wav"): "/local/sneeze.wav"}


def test_a_failed_upload_stops_the_app_and_names_the_sound(fake_reachy_mini, caplog):
    fake_reachy_mini.media.audio.upload_sound.side_effect = OSError("daemon unreachable")

    with caplog.at_level(logging.ERROR), pytest.raises(OSError):
        upload_sounds([move_with_sounds("/local/sneeze.wav")], fake_reachy_mini)

    assert "Could not upload sneeze.wav, a sound of sneezing" in caplog.text

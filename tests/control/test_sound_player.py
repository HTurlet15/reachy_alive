"""Unit tests for SoundPlayer: its thread starts the sounds, in order."""

import logging
import threading
import time
from pathlib import Path

from reachy_alive.control.sound_player import SoundPlayer

SNEEZE = Path("/local/sneeze.wav")
RELIEF = Path("/local/relief.wav")
ROBOT_SOUNDS = {SNEEZE: "/robot/sneeze.wav", RELIEF: "/robot/relief.wav"}


def test_starts_each_sound_from_where_the_robot_finds_it_in_order(fake_reachy_mini):
    player = SoundPlayer(fake_reachy_mini, ROBOT_SOUNDS)
    player.start()

    player.play(SNEEZE)
    player.play(RELIEF)
    player.stop()

    played = [call.args[0] for call in fake_reachy_mini.media.play_sound.call_args_list]
    assert played == ["/robot/sneeze.wav", "/robot/relief.wav"]


def test_play_returns_at_once_while_the_robot_is_slow(fake_reachy_mini):
    robot_answers = threading.Event()
    fake_reachy_mini.media.play_sound.side_effect = lambda _: robot_answers.wait(1.0)
    player = SoundPlayer(fake_reachy_mini, ROBOT_SOUNDS)
    player.start()

    started = time.perf_counter()
    player.play(SNEEZE)
    took_s = time.perf_counter() - started

    robot_answers.set()
    player.stop()
    assert took_s < 0.005


def test_a_failing_sound_is_logged_and_the_next_one_still_plays(fake_reachy_mini, caplog):
    fake_reachy_mini.media.play_sound.side_effect = [RuntimeError("daemon gone"), None]
    player = SoundPlayer(fake_reachy_mini, ROBOT_SOUNDS)
    player.start()

    with caplog.at_level(logging.ERROR, logger="reachy_alive"):
        player.play(SNEEZE)
        player.play(RELIEF)
        player.stop()

    assert "Could not play sneeze.wav" in caplog.text
    fake_reachy_mini.media.play_sound.assert_called_with("/robot/relief.wav")


def test_stop_ends_the_thread(fake_reachy_mini):
    player = SoundPlayer(fake_reachy_mini, ROBOT_SOUNDS)
    player.start()

    player.stop()

    assert not player._thread.is_alive()

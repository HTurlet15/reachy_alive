# tests/moves/test_sneezing.py
"""Unit tests for Sneezing.

The head comes from a fake recording (see conftest.py). The play test runs
the real motion loop without mocking time.sleep, so it lasts as long as
the gesture itself.
"""

import pytest

from reachy_alive.moves.sneezing import Sneezing


def test_play_uploads_sounds_streams_poses_and_returns_to_neutral(
    fake_reachy_mini, fake_library
):
    Sneezing(fake_library).play(fake_reachy_mini)

    assert fake_reachy_mini.media.audio.upload_sound.call_count == 5
    assert fake_reachy_mini.media.play_sound.call_count == 5  # one per phase
    assert fake_reachy_mini.set_target.called
    fake_reachy_mini.play_move.assert_not_called()  # the recording's own sound
    fake_reachy_mini.goto_target.assert_called_once()  # play()'s return to neutral


def test_head_and_body_come_from_the_recording(fake_library, fake_recording):
    sneezing = Sneezing(fake_library)

    head, _, body_yaw = sneezing._pose_at("inhale1", 0.5, 0, elapsed_s=0.5)

    assert head is fake_recording.HEAD
    assert body_yaw == fake_recording.BODY_YAW_RAD


def test_head_is_never_read_at_or_past_the_recording_end(fake_library, fake_recording):
    sneezing = Sneezing(fake_library)
    fake_recording.timestamps = [0.0, sneezing.duration_s]  # ends with the phases

    sneezing._pose_at("relief", 1.0, 0, elapsed_s=sneezing.duration_s)

    assert fake_recording.evaluated_at[-1] < sneezing.duration_s


def _antenna(sneezing, phase, p, elapsed_s):
    _, antennas, _ = sneezing._pose_at(phase, p, 0, elapsed_s)
    return antennas[0]


@pytest.mark.parametrize("phase_before, phase_after", [("inhale3", "sneeze"), ("sneeze", "relief")])
def test_antennas_dont_jump_between_phases(fake_library, phase_before, phase_after):
    sneezing = Sneezing(fake_library)
    boundary_s = sneezing.phase_ends_s[phase_before]

    end_of_before = _antenna(sneezing, phase_before, 1.0, boundary_s)
    start_of_after = _antenna(sneezing, phase_after, 0.0, boundary_s)

    assert start_of_after == pytest.approx(end_of_before)


def test_antennas_end_where_go_neutral_expects_them(fake_library):
    sneezing = Sneezing(fake_library)

    antenna = _antenna(sneezing, "relief", 1.0, sneezing.duration_s)

    assert antenna == pytest.approx(Sneezing.ANTENNA_START_RAD)


def test_antennas_drop_to_the_sneeze_angle_in_a_few_ticks(fake_library):
    sneezing = Sneezing(fake_library)
    sneeze_start_s = sneezing.phase_ends_s["inhale3"]

    antenna = _antenna(
        sneezing, "sneeze", 0.5, sneeze_start_s + Sneezing.SNEEZE_DROP_DURATION_S
    )

    assert antenna == pytest.approx(Sneezing.ANTENNA_SNEEZE_RAD)

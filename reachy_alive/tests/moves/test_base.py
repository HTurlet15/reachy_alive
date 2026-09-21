from pathlib import Path

from reachy_alive.moves.base import Move


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
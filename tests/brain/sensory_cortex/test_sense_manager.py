"""Unit tests for what SenseManager does between senses and detectors: no robot needed."""

import sys
import threading

import pytest

from reachy_alive.brain.sensory_cortex import vision
from reachy_alive.brain.sensory_cortex.sense_manager import SenseManager
from reachy_alive.brain.sensory_cortex.vision.face_presence_detector import FacePresenceDetector
from reachy_alive.shared_state import VisionFacts

# Finding the detectors


def test_the_vision_folder_holds_the_face_presence_detector():
    facts = VisionFacts()

    detectors = SenseManager.find_detectors(vision, facts)

    assert [type(detector) for detector in detectors] == [FacePresenceDetector]


@pytest.fixture
def made_up_sense(tmp_path, monkeypatch):
    """A sense folder written on the fly: two detector files, and a helper file."""
    package = tmp_path / "made_up_sense"
    package.mkdir()
    (package / "__init__.py").write_text("")
    (package / "clap_detector.py").write_text(
        "class ClapDetector:\n"
        "    def __init__(self, facts):\n"
        "        self.facts = facts\n"
    )
    (package / "snap_detector.py").write_text(
        "from made_up_sense.clap_detector import ClapDetector  # imported: not found twice\n"
        "class SnapDetector:\n"
        "    def __init__(self, facts):\n"
        "        self.facts = facts\n"
    )
    (package / "helpers.py").write_text(
        "class HelperDetector:  # not in a *_detector.py file: ignored\n"
        "    def __init__(self, facts):\n"
        "        pass\n"
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    yield __import__("made_up_sense")
    for name in [name for name in sys.modules if name.startswith("made_up_sense")]:
        del sys.modules[name]


def test_only_detector_classes_of_detector_files_are_found_once(made_up_sense):
    detectors = SenseManager.find_detectors(made_up_sense, facts="the facts")

    assert sorted(type(detector).__name__ for detector in detectors) == ["ClapDetector", "SnapDetector"]


def test_every_detector_is_given_the_sense_facts(made_up_sense):
    detectors = SenseManager.find_detectors(made_up_sense, facts="the facts")

    assert all(detector.facts == "the facts" for detector in detectors)


# Handing frames on


class ScriptedSense:
    """Gives the frames it is told to, then stops the watch."""

    PERIOD_S = 0.0

    def __init__(self, frames: list, stop_event: threading.Event) -> None:
        self._frames = list(frames)
        self._stop_event = stop_event

    def read_once(self, now: float):
        frame = self._frames.pop(0)
        if not self._frames:
            self._stop_event.set()
        return frame


class RecordingDetector:
    """Keeps every frame it is handed."""

    def __init__(self) -> None:
        self.frames: list = []

    def update(self, frame) -> None:
        self.frames.append(frame)


def test_every_detector_gets_every_frame_in_order():
    stop_event = threading.Event()
    sense = ScriptedSense(["frame 1", "frame 2"], stop_event)
    detectors = [RecordingDetector(), RecordingDetector()]

    SenseManager.watch(sense, detectors, stop_event)

    assert detectors[0].frames == detectors[1].frames == ["frame 1", "frame 2"]


def test_a_missing_frame_is_skipped():
    stop_event = threading.Event()
    sense = ScriptedSense([None, "frame"], stop_event)
    detector = RecordingDetector()

    SenseManager.watch(sense, [detector], stop_event)

    assert detector.frames == ["frame"]
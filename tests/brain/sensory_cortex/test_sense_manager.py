"""Unit tests for what SenseManager does between senses and detectors: no robot needed."""

import sys
import threading
from unittest.mock import MagicMock

import pytest

from reachy_alive.brain.sensory_cortex import vision
from reachy_alive.brain.sensory_cortex.sense import Sense
from reachy_alive.brain.sensory_cortex.sense_manager import SenseManager
from reachy_alive.brain.sensory_cortex.vision.face_presence_detector import FacePresenceDetector
from reachy_alive.shared_state import SharedState, VisionFacts

# Finding the detectors


def test_the_vision_folder_holds_the_face_presence_detector():
    facts = VisionFacts()

    detectors = SenseManager.find_detectors(vision, facts)

    assert [type(detector) for detector in detectors] == [FacePresenceDetector]


@pytest.fixture
def made_up_sense(tmp_path, monkeypatch):
    """A sense folder written on the fly: two detector files, a broken one, and a helper file."""
    detector_import = "from reachy_alive.brain.sensory_cortex.detector import Detector\n"
    package = tmp_path / "made_up_sense"
    package.mkdir()
    (package / "__init__.py").write_text("")
    (package / "clap_detector.py").write_text(
        detector_import
        + "class ClapDetector(Detector):\n"
        "    def _detect(self, features):\n"
        "        pass\n"
    )
    (package / "snap_detector.py").write_text(
        detector_import
        + "from made_up_sense.clap_detector import ClapDetector  # imported: not found twice\n"
        "class SnapDetector(Detector):\n"
        "    def _detect(self, features):\n"
        "        pass\n"
        "class SnapCounterDetector:  # named like one, but not a Detector: ignored\n"
        "    pass\n"
    )
    (package / "broken_detector.py").write_text(
        "import a_module_that_does_not_exist  # a contributor's mistake\n"
    )
    (package / "helpers.py").write_text(
        detector_import
        + "class HelperDetector(Detector):  # not in a *_detector.py file: ignored\n"
        "    def _detect(self, features):\n"
        "        pass\n"
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    yield __import__("made_up_sense")
    for name in [name for name in sys.modules if name.startswith("made_up_sense")]:
        del sys.modules[name]


def test_only_detectors_written_in_detector_files_are_found_once(made_up_sense):
    detectors = SenseManager.find_detectors(made_up_sense, facts="the facts")

    names = sorted(type(detector).__name__ for detector in detectors)
    assert names == ["ClapDetector", "SnapDetector"]


def test_a_detector_file_that_fails_to_load_is_skipped(made_up_sense, caplog):
    detectors = SenseManager.find_detectors(made_up_sense, facts="the facts")

    assert len(detectors) == 2
    assert "broken_detector can't be loaded: skipped" in caplog.text


def test_every_detector_is_given_the_sense_facts(made_up_sense):
    detectors = SenseManager.find_detectors(made_up_sense, facts="the facts")

    assert all(detector._facts == "the facts" for detector in detectors)


# Handing features on


class ScriptedSense(Sense):
    """Gives the features it is told to, then stops the watch. Notes when opened and closed."""

    def __init__(self, features: list, stop_event: threading.Event) -> None:
        super().__init__(MagicMock(), SharedState())
        self._features = list(features)
        self._stop_event = stop_event
        self.events: list[str] = []

    def open(self) -> None:
        self.events.append("open")

    def close(self) -> None:
        self.events.append("close")

    def _perceive(self, perceived_at: float, robot_moving_itself: bool):
        self.events.append("read")
        features = self._features.pop(0)
        if not self._features:
            self._stop_event.set()
        return features


class RecordingDetector:
    """Keeps all the features it is handed."""

    def __init__(self) -> None:
        self.features: list = []

    def update(self, features) -> None:
        self.features.append(features)


def test_every_detector_gets_all_the_features_in_order():
    stop_event = threading.Event()
    sense = ScriptedSense(["features 1", "features 2"], stop_event)
    detectors = [RecordingDetector(), RecordingDetector()]

    SenseManager.watch(sense, detectors, stop_event)

    assert detectors[0].features == detectors[1].features == ["features 1", "features 2"]


def test_a_reading_without_features_is_skipped():
    stop_event = threading.Event()
    sense = ScriptedSense([None, "features"], stop_event)
    detector = RecordingDetector()

    SenseManager.watch(sense, [detector], stop_event)

    assert detector.features == ["features"]


def test_the_sense_is_opened_before_reading_and_closed_after():
    stop_event = threading.Event()
    sense = ScriptedSense(["features 1", "features 2"], stop_event)

    SenseManager.watch(sense, [], stop_event)

    assert sense.events == ["open", "read", "read", "close"]


def test_a_sense_that_fails_is_logged_and_closed(caplog):
    stop_event = threading.Event()
    sense = ScriptedSense([], stop_event)  # no features to give: read_once fails

    SenseManager.watch(sense, [], stop_event)

    assert sense.events == ["open", "read", "close"]
    assert "ScriptedSense failed: stopped" in caplog.text


class FailingDetector:
    """Fails on any features, like a detector with a bug."""

    def __init__(self) -> None:
        self.calls = 0

    def update(self, features) -> None:
        self.calls += 1
        raise ValueError("a bug")


def test_a_failing_detector_does_not_stop_the_others(caplog):
    stop_event = threading.Event()
    sense = ScriptedSense(["features 1", "features 2"], stop_event)
    failing, working = FailingDetector(), RecordingDetector()

    SenseManager.watch(sense, [failing, working], stop_event)

    assert working.features == ["features 1", "features 2"]
    assert "FailingDetector failed: switched off" in caplog.text


def test_a_failing_detector_is_switched_off_after_its_first_failure():
    stop_event = threading.Event()
    sense = ScriptedSense(["features 1", "features 2", "features 3"], stop_event)
    failing = FailingDetector()

    SenseManager.watch(sense, [failing], stop_event)

    assert failing.calls == 1

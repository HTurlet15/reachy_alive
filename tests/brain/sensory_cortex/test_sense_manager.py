"""Unit tests for what SenseManager does between senses and detectors: no robot needed."""

import sys
import threading
import time
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
        "    def forget(self):\n"
        "        pass\n"
    )
    (package / "snap_detector.py").write_text(
        detector_import
        + "from made_up_sense.clap_detector import ClapDetector  # imported: not found twice\n"
        "class SnapDetector(Detector):\n"
        "    def _detect(self, features):\n"
        "        pass\n"
        "    def forget(self):\n"
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
    """Gives the features it is told to, then stops the run. Counts its readings."""

    NAME = "scripted"

    def __init__(self, features: list, stop_event: threading.Event) -> None:
        super().__init__(MagicMock(), SharedState())
        self._features = list(features)
        self._stop_event = stop_event
        self.readings = 0

    def _extract_features(self, perceived_at: float, robot_moving_itself: bool):
        self.readings += 1
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

    SenseManager.run_sense(sense, detectors, stop_event)

    assert detectors[0].features == detectors[1].features == ["features 1", "features 2"]


def test_a_reading_without_features_is_skipped():
    stop_event = threading.Event()
    sense = ScriptedSense([None, "features"], stop_event)
    detector = RecordingDetector()

    SenseManager.run_sense(sense, [detector], stop_event)

    assert detector.features == ["features"]


def test_a_sense_that_fails_is_logged_and_stopped(caplog):
    stop_event = threading.Event()
    sense = ScriptedSense([], stop_event)  # no features to give: perceive fails

    SenseManager.run_sense(sense, [], stop_event)

    assert sense.readings == 1
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

    SenseManager.run_sense(sense, [failing, working], stop_event)

    assert working.features == ["features 1", "features 2"]
    assert "FailingDetector failed: switched off" in caplog.text


def test_a_failing_detector_is_switched_off_after_its_first_failure():
    stop_event = threading.Event()
    sense = ScriptedSense(["features 1", "features 2", "features 3"], stop_event)
    failing = FailingDetector()

    SenseManager.run_sense(sense, [failing], stop_event)

    assert failing.calls == 1


# Switching a sense off and on


def test_a_sense_without_parts_is_named_after_itself():
    sense = ScriptedSense([], threading.Event())

    assert sense.names() == ["scripted"]



class EndlessSense(Sense):
    """Gives features at every reading, until the run stops."""

    NAME = "endless"
    PERIOD_S = 0.01

    def __init__(self, shared_state: SharedState) -> None:
        super().__init__(MagicMock(), shared_state)

    def _extract_features(self, perceived_at: float, robot_moving_itself: bool):
        return "features"


class ForgetfulDetector(RecordingDetector):
    """Keeps all the features it is handed, and counts how often it forgot."""

    def __init__(self) -> None:
        super().__init__()
        self.forgotten = 0

    def forget(self) -> None:
        self.forgotten += 1


def wait_until(condition, timeout_s: float = 2.0) -> None:
    """Wait until condition() is true: the sense runs in its own thread."""
    deadline = time.monotonic() + timeout_s
    while not condition():
        assert time.monotonic() < deadline, "waited too long"
        time.sleep(0.005)


class RunningSense:
    """An EndlessSense and its detector, run in a thread as SenseManager.start does."""

    def __init__(self) -> None:
        self.shared_state = SharedState()
        self.sense = EndlessSense(self.shared_state)
        self.detector = ForgetfulDetector()
        self._stop_event = threading.Event()
        self._thread = threading.Thread(
            target=SenseManager.run_sense, args=(self.sense, [self.detector], self._stop_event)
        )

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        self._thread.join(timeout=1.0)

    def switch(self, enabled: bool) -> None:
        """Switch the sense on or off, as the page does."""
        self.shared_state.set_sense_enabled(EndlessSense.NAME, enabled)


@pytest.fixture
def running(monkeypatch):
    """A running sense that checks often whether it is back on, stopped after the test."""
    monkeypatch.setattr(SenseManager, "OFF_CHECK_S", 0.01)
    running = RunningSense()
    yield running
    running.stop()


def test_the_detectors_of_a_sense_switched_off_forget(running):
    running.start()
    wait_until(lambda: running.detector.features)

    running.switch(False)

    wait_until(lambda: running.detector.forgotten >= 1)


def test_a_sense_switched_off_is_not_read(running):
    running.start()
    running.switch(False)
    wait_until(lambda: running.detector.forgotten >= 1)
    read_before = len(running.detector.features)

    time.sleep(0.05)  # five readings, were it still read

    assert len(running.detector.features) == read_before


def test_a_sense_switched_back_on_is_read_again(running):
    running.start()
    running.switch(False)
    wait_until(lambda: running.detector.forgotten >= 1)
    read_while_off = len(running.detector.features)

    running.switch(True)

    wait_until(lambda: len(running.detector.features) > read_while_off)


def test_a_sense_switched_off_from_the_start_is_never_read(running):
    running.switch(False)
    running.start()

    time.sleep(0.05)

    assert running.detector.features == []

"""SenseManager: runs the robot's senses, and carries their features to the detectors.

A sense describes each reading of its sensor by its features. A detector reads
them and records facts. Neither knows the other: SenseManager carries the features.
Any `*_detector.py` file in a sense's folder is one of its detectors.
"""

import importlib
import inspect
import logging
import pkgutil
import threading
import time
from types import ModuleType

from reachy_mini import ReachyMini

from reachy_alive.brain.sensory_cortex import hearing, inertial, touch, vision
from reachy_alive.brain.sensory_cortex.detector import Detector
from reachy_alive.brain.sensory_cortex.hearing.hearing_sense import HearingSense
from reachy_alive.brain.sensory_cortex.inertial.inertial_sense import InertialSense
from reachy_alive.brain.sensory_cortex.sense import Sense
from reachy_alive.brain.sensory_cortex.touch.touch_sense import TouchSense
from reachy_alive.brain.sensory_cortex.vision.vision_sense import VisionSense
from reachy_alive.shared_state import SharedState

logger = logging.getLogger(__name__)


class SenseManager:
    """Owns the robot's senses, each in its own thread. Never drives the robot."""

    # A sense stuck in a call must not hang the app's shutdown.
    STOP_TIMEOUT_S = 1.0
    # How often a sense switched off checks whether the page switched it back on.
    OFF_CHECK_S = 0.2

    def __init__(self, reachy_mini: ReachyMini, shared_state: SharedState) -> None:
        """Build every sense, and find the detectors of each.

        Args:
            reachy_mini: Connected robot instance, only read.
            shared_state: Where the senses and their detectors record facts.
        """
        # Each sense with its detectors, found in the sense's folder.
        self._senses = [
            (
                VisionSense(reachy_mini, shared_state),
                self.find_detectors(vision, shared_state.vision),
            ),
            (
                InertialSense(reachy_mini, shared_state),
                self.find_detectors(inertial, shared_state.inertial),
            ),
            (TouchSense(reachy_mini, shared_state), self.find_detectors(touch, shared_state.touch)),
            (
                HearingSense(reachy_mini, shared_state),
                self.find_detectors(hearing, shared_state.hearing),
            ),
        ]
        self._threads: list[threading.Thread] = []

    def sense_names(self) -> list[str]:
        """Return what the page can switch off, available or not: each sense, or its parts."""
        names = []
        for sense, _ in self._senses:
            names += sense.names()
        return names

    def start(self, stop_event: threading.Event) -> None:
        """Start one thread per sense, each running run_sense until stop_event is set."""
        for sense, detectors in self._senses:
            sense_name = type(sense).__name__
            if not sense.is_available():
                logger.info("%s has nothing to read: not started", sense_name)
                continue
            logger.info("%s detectors: %s", sense_name, [type(d).__name__ for d in detectors])
            thread = threading.Thread(
                target=SenseManager.run_sense,
                args=(sense, detectors, stop_event),
                name=sense_name,
                daemon=True,
            )
            thread.start()
            self._threads.append(thread)

    def join(self) -> None:
        """Wait for every sense to stop, STOP_TIMEOUT_S at most each."""
        for thread in self._threads:
            thread.join(timeout=self.STOP_TIMEOUT_S)

    @staticmethod
    def find_detectors(sense_folder: ModuleType, facts) -> list:
        """Build each detector of a sense's folder, giving it the sense's facts.

        A detector is a class that inherits Detector, written in a
        `*_detector.py` file of that folder. A file that fails to load is skipped, so the
        other detectors still run.
        """
        detectors = []
        for file in pkgutil.iter_modules(sense_folder.__path__):
            if not file.name.endswith("_detector"):
                continue
            try:
                module = importlib.import_module(f"{sense_folder.__name__}.{file.name}")
                detectors += [
                    cls(facts)
                    for _, cls in inspect.getmembers(module, inspect.isclass)
                    # cls.__module__: written in this file, not imported into it
                    if issubclass(cls, Detector) and cls.__module__ == module.__name__
                ]
            except Exception:
                logger.exception("%s can't be loaded: skipped", file.name)
        return detectors

    @staticmethod
    def run_sense(sense: Sense, detectors: list, stop_event: threading.Event) -> None:
        """Run a sense until stop_event is set, handing the features it perceives to its detectors.

        Each turn, while the page has the sense switched on: perceive, hand the
        features to every detector, then wait for the rest of PERIOD_S. Switched
        off, the sense isn't read, so it costs nothing, and its detectors forget
        what they knew: forgetting again changes nothing. A sense that fails is
        logged and stopped. A detector that fails is switched off, so the sense
        and the other detectors keep going.

        Args:
            sense: The sense to run.
            detectors: Each has update(features) and forget().
            stop_event: Set externally to stop the sense.
        """
        try:
            while not stop_event.is_set():
                if not sense.is_enabled():
                    SenseManager._make_detectors_forget(detectors)
                    stop_event.wait(SenseManager.OFF_CHECK_S)  # wakes at once on stop
                    continue

                started_at = time.monotonic()
                features = sense.perceive(started_at)
                if features is not None:
                    SenseManager._update_detectors(features, detectors)
                elapsed_s = time.monotonic() - started_at
                stop_event.wait(max(0.0, sense.PERIOD_S - elapsed_s))  # wakes at once on stop
        except Exception:
            logger.exception("%s failed: stopped", type(sense).__name__)

    @staticmethod
    def _update_detectors(features, detectors: list) -> None:
        """Hand the features of one reading to every detector, and switch off any that fails."""
        for detector in list(detectors):  # a copy: failing ones leave the list
            try:
                detector.update(features)
            except Exception:
                logger.exception("%s failed: switched off", type(detector).__name__)
                detectors.remove(detector)

    @staticmethod
    def _make_detectors_forget(detectors: list) -> None:
        """Make every detector forget what it knew, and switch off any that fails."""
        for detector in list(detectors):  # a copy: failing ones leave the list
            try:
                detector.forget()
            except Exception:
                logger.exception("%s failed: switched off", type(detector).__name__)
                detectors.remove(detector)

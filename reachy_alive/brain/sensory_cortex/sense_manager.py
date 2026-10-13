"""SenseManager: runs the robot's senses, and carries their frames to the detectors.

A sense describes what it perceives as a frame. A detector reads frames and
records facts. Neither knows the other: SenseManager carries the frames.
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

from reachy_alive.brain.sensory_cortex import inertial, touch, vision
from reachy_alive.brain.sensory_cortex.hearing import HearingSense
from reachy_alive.brain.sensory_cortex.inertial.inertial_sense import InertialSense
from reachy_alive.brain.sensory_cortex.touch.touch_sense import TouchSense
from reachy_alive.brain.sensory_cortex.vision.vision_sense import VisionSense
from reachy_alive.shared_state import SharedState

logger = logging.getLogger(__name__)


class SenseManager:
    """Owns the robot's senses, each in its own thread. Never drives the robot."""

    # A sense stuck in a call must not hang the app's shutdown.
    STOP_TIMEOUT_S = 1.0

    def __init__(self, reachy_mini: ReachyMini, shared_state: SharedState) -> None:
        """Build every sense, and find the detectors of each.

        Args:
            reachy_mini: Connected robot instance, only read.
            shared_state: Where the senses and their detectors record facts.
        """
        # Each sense with its detectors, found in the sense's folder.
        self._senses = [
            (VisionSense(reachy_mini, shared_state), self.find_detectors(vision, shared_state.vision)),
            (
                InertialSense(reachy_mini, shared_state),
                self.find_detectors(inertial, shared_state.inertial),
            ),
            (TouchSense(reachy_mini, shared_state), self.find_detectors(touch, shared_state.touch)),
        ]
        # Not yet split into a sense and its detectors: each runs its own loop.
        self._older_senses = [
            HearingSense(reachy_mini, shared_state),
        ]
        self._threads: list[threading.Thread] = []

    def start(self, stop_event: threading.Event) -> None:
        """Start one thread per sense. Each stops once stop_event is set."""
        for sense in self._older_senses:
            self._start_thread(sense, sense.run, stop_event)

        for sense, detectors in self._senses:
            sense_name = type(sense).__name__
            if not sense.is_available():
                logger.info("%s has nothing to read: not started", sense_name)
                continue
            logger.info("%s detectors: %s", sense_name, [type(d).__name__ for d in detectors])
            self._start_thread(sense, SenseManager.watch, sense, detectors, stop_event)

    def join(self) -> None:
        """Wait for every sense to stop, STOP_TIMEOUT_S at most each."""
        for thread in self._threads:
            thread.join(timeout=self.STOP_TIMEOUT_S)

    @staticmethod
    def find_detectors(sense_folder: ModuleType, facts) -> list:
        """Build each detector of a sense's folder, giving it the sense's facts.

        A detector is a class named `…Detector`, written in a `*_detector.py`
        file of that folder. A file that fails to load is skipped, so the
        other detectors still run.
        """
        detectors = []
        for file in pkgutil.iter_modules(sense_folder.__path__):
            if not file.name.endswith("_detector"):
                continue
            try:
                detectors += SenseManager._build_detectors(f"{sense_folder.__name__}.{file.name}", facts)
            except Exception:
                logger.exception("%s can't be loaded: skipped", file.name)
        return detectors

    @staticmethod
    def watch(sense, detectors: list, stop_event: threading.Event) -> None:
        """Read the sense every PERIOD_S, and hand each frame to every detector.

        A detector that fails is switched off, so the sense and the other
        detectors keep going.

        Args:
            sense: Has a PERIOD_S, and read_once(now) giving a frame or None.
            detectors: Each has update(frame).
            stop_event: Set externally to stop watching.
        """
        while not stop_event.is_set():
            started_at = time.monotonic()
            frame = sense.read_once(started_at)
            if frame is not None:
                SenseManager._hand_frame(frame, detectors)
            elapsed_s = time.monotonic() - started_at
            stop_event.wait(max(0.0, sense.PERIOD_S - elapsed_s))  # wakes at once on stop

    @staticmethod
    def _build_detectors(module_name: str, facts) -> list:
        """Import a detector file, and build each detector class written in it."""
        module = importlib.import_module(module_name)
        return [
            cls(facts)
            for name, cls in inspect.getmembers(module, inspect.isclass)
            if name.endswith("Detector") and cls.__module__ == module.__name__  # not imported
        ]

    @staticmethod
    def _hand_frame(frame, detectors: list) -> None:
        """Hand one frame to every detector, and switch off any that fails."""
        for detector in list(detectors):  # a copy: failing ones leave the list
            try:
                detector.update(frame)
            except Exception:
                logger.exception("%s failed: switched off", type(detector).__name__)
                detectors.remove(detector)

    def _start_thread(self, sense, target, *args) -> None:
        """Run target(*args) in a thread named after the sense, and keep it to join."""
        thread = threading.Thread(target=target, args=args, name=type(sense).__name__, daemon=True)
        thread.start()
        self._threads.append(thread)
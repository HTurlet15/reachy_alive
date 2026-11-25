"""The voice model: how much sound sounds like a voice, from Silero VAD.

Silero VAD is a small neural network trained to tell a voice from other
sounds by its shape, not its loudness. Its file, `assets/models/silero_vad.onnx`,
holds what it learned; onnxruntime runs it.
"""

from pathlib import Path

import numpy as np
import onnxruntime

MODEL_PATH = Path(__file__).resolve().parents[3] / "assets" / "models" / "silero_vad.onnx"


class VoiceModel:
    """Hears sound in pieces of any length, and says how much it sounds like a voice.

    The model judges 512 samples (32 ms) at a time, back to back, and
    remembers what it heard before: each sample must reach it once, in order.
    """

    SAMPLE_RATE_HZ = 16_000
    CHUNK_SAMPLES = 512
    # Silero was trained on each chunk preceded by the last 64 samples (4 ms)
    # of the one before: its utils_vad.py does so (silero-vad 6.3). Nothing in
    # the model file says it. Without them, it heard no voice at all in our
    # recordings of someone talking.
    PREVIOUS_END_SAMPLES = 64

    def __init__(self, session: onnxruntime.InferenceSession | None = None) -> None:
        """Load the model, and start having heard nothing.

        Args:
            session: The model to run; Silero's, loaded from its file, by
                default. Tests pass a fake one.
        """
        if session is None:
            options = onnxruntime.SessionOptions()
            # One thread, as Silero's own code does: the model is small, and the
            # robot's other parts need the processor's other cores.
            options.intra_op_num_threads = 1
            options.inter_op_num_threads = 1
            session = onnxruntime.InferenceSession(str(MODEL_PATH), sess_options=options)
        self._session = session
        self.forget()

    def forget(self) -> None:
        """Forget what was heard: the next sound starts after a silence."""
        # The model's memory of what it heard: two rows of 128 numbers for our
        # one sound, that only the model understands. Nothing heard yet.
        self._memory = np.zeros((2, 1, 128), np.float32)
        # Silence before the first chunk.
        self._previous_chunk = np.zeros((1, self.CHUNK_SAMPLES), np.float32)
        # Samples heard, waiting to make a full chunk.
        self._waiting_samples = np.zeros(0, np.float32)
        self._latest_probability = 0.0

    def hear(self, samples: np.ndarray) -> float:
        """Hear the next samples, and return how much the latest full chunk sounds like a voice.

        Args:
            samples: The next sound, any number of samples between -1 and 1,
                at 16,000 samples per second.

        Returns:
            From 0 (no voice) to 1 (a voice). Until a first full chunk, 0.
        """
        self._waiting_samples = np.concatenate([self._waiting_samples, samples.astype(np.float32)])
        while len(self._waiting_samples) >= self.CHUNK_SAMPLES:
            chunk = self._waiting_samples[: self.CHUNK_SAMPLES]
            self._waiting_samples = self._waiting_samples[self.CHUNK_SAMPLES :]
            self._latest_probability = self._probability_of(chunk)
        return self._latest_probability

    def _probability_of(self, chunk: np.ndarray) -> float:
        """Run the model on one chunk, right after the previous one, and return its probability."""
        # The model judges a table of sounds, one row each: ours is a table of one row.
        chunk_as_row = chunk.reshape(1, self.CHUNK_SAMPLES)
        previous_end = self._previous_chunk[:, -self.PREVIOUS_END_SAMPLES :]
        model_input = np.concatenate([previous_end, chunk_as_row], axis=1)  # 64 + 512 samples
        # None: return every output, here the probability and the new memory.
        probability, self._memory = self._session.run(
            None,
            {
                "input": model_input,
                "state": self._memory,
                "sr": np.array(self.SAMPLE_RATE_HZ, np.int64),
            },
        )
        self._previous_chunk = chunk_as_row
        # A table too: one row, one column.
        return float(probability[0, 0])

# scripts/compose_sound.py
"""Concatenate several .wav files into one, with silences between them."""

import numpy as np
import soundfile as sf


def concatenate(parts: list[tuple[str, float]], output_path: str) -> None:
    """Join .wav files into one.

    Args:
        parts: (path, silence_after_seconds) pairs, in order.
        output_path: Where to write the result.
    """
    segments = []
    sample_rate = None

    for path, silence_s in parts:
        audio, rate = sf.read(path)
        if sample_rate is None:
            sample_rate = rate
        elif rate != sample_rate:
            raise ValueError(f"{path} has sample rate {rate}, expected {sample_rate}")

        segments.append(audio)
        if silence_s > 0:
            segments.append(np.zeros(int(silence_s * sample_rate)))

    sf.write(output_path, np.concatenate(segments), sample_rate)
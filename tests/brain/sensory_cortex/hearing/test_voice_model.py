"""Unit tests for VoiceModel: Silero's model, fed 512 samples at a time, in order.

A fake model checks what reaches it; Silero's own checks it hears no voice
where there is none. That it hears a voice was checked on recordings of the
robot, which stay out of the repo.
"""

import numpy as np

from reachy_alive.brain.sensory_cortex.hearing.voice_model import VoiceModel

CHUNK = VoiceModel.CHUNK_SAMPLES


class FakeModel:
    """Records each input; answers the call number as the probability, and counts in its memory."""

    def __init__(self):
        self.inputs = []

    def run(self, output_names, inputs):
        self.inputs.append(inputs)
        probability = np.array([[len(self.inputs) / 10]], np.float32)
        new_memory = inputs["state"] + 1
        return [probability, new_memory]


def counting(start, count):
    """Samples numbered start, start + 1…: where each one went can be read back."""
    return np.arange(start, start + count, dtype=np.float32)


def test_nothing_runs_before_a_full_chunk():
    fake = FakeModel()
    voice = VoiceModel(session=fake)

    probability = voice.hear(counting(0, CHUNK - 1))

    assert fake.inputs == []
    assert probability == 0.0


def test_each_chunk_follows_the_end_of_the_previous_one():
    fake = FakeModel()
    voice = VoiceModel(session=fake)

    voice.hear(counting(0, 2 * CHUNK))

    first, second = (inputs["input"] for inputs in fake.inputs)
    assert first.shape == (1, 64 + CHUNK)
    np.testing.assert_array_equal(first[0, :64], np.zeros(64))  # silence before the first
    np.testing.assert_array_equal(first[0, 64:], counting(0, CHUNK))
    np.testing.assert_array_equal(second[0, :64], counting(CHUNK - 64, 64))
    np.testing.assert_array_equal(second[0, 64:], counting(CHUNK, CHUNK))


def test_pieces_of_any_length_reach_the_model_in_order_each_sample_once():
    fake = FakeModel()
    voice = VoiceModel(session=fake)

    for start in range(0, 15 * 320, 320):  # 15 frames of 20 ms, as the hearing sense cuts them
        voice.hear(counting(start, 320))

    heard = np.concatenate([inputs["input"][0, 64:] for inputs in fake.inputs])
    np.testing.assert_array_equal(heard, counting(0, len(heard)))
    assert len(fake.inputs) == 9  # 4,800 samples: 9 full chunks, the rest waits


def test_the_model_gets_back_the_memory_it_returned():
    fake = FakeModel()
    voice = VoiceModel(session=fake)

    voice.hear(counting(0, 3 * CHUNK))

    memories = [inputs["state"][0, 0, 0] for inputs in fake.inputs]
    assert memories == [0.0, 1.0, 2.0]


def test_the_latest_chunk_gives_the_probability():
    voice = VoiceModel(session=FakeModel())

    assert voice.hear(counting(0, 2 * CHUNK)) == np.float32(0.2)
    assert voice.hear(counting(0, 10)) == np.float32(0.2)  # no new chunk yet


def test_forgetting_starts_again_after_a_silence():
    fake = FakeModel()
    voice = VoiceModel(session=fake)
    voice.hear(counting(0, CHUNK + 100))

    voice.forget()
    voice.hear(counting(1000, CHUNK))

    after = fake.inputs[-1]
    np.testing.assert_array_equal(after["input"][0, :64], np.zeros(64))
    np.testing.assert_array_equal(after["input"][0, 64:], counting(1000, CHUNK))
    assert after["state"].max() == 0.0


def test_silero_hears_no_voice_in_silence():
    voice = VoiceModel()

    probability = voice.hear(np.zeros(VoiceModel.SAMPLE_RATE_HZ, np.float32))  # 1 s

    assert probability < 0.1


def test_silero_hears_no_voice_in_steady_noise():
    rng = np.random.default_rng(seed=0)
    voice = VoiceModel()

    probabilities = [
        voice.hear(rng.normal(0.0, 0.05, 320).astype(np.float32)) for _ in range(100)
    ]  # 2 s of hiss

    assert max(probabilities) < 0.5

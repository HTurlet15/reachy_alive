# Models

Trained models the app runs, with onnxruntime.

| File              | What it does                                     | Where it comes from                                                                                                                                                                                                            | License                                              |
| ----------------- | ------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ---------------------------------------------------- |
| `silero_vad.onnx` | Says how much 32 ms of sound sounds like a voice | [Silero VAD](https://github.com/snakers4/silero-vad), version 6.3, copied from the `silero-vad` Python package (`silero_vad/data/silero_vad.onnx`), SHA-256 `f6f4407b41e05e277e7f5cfd9b9ae957b1dfe763c6076a934734c0b448e09b31` | MIT, in [`silero_vad_LICENSE`](./silero_vad_LICENSE) |

The model file is copied rather than installed: the `silero-vad` package
needs PyTorch, hundreds of megabytes the app would never use.
`hearing/voice_model.py` runs it the way Silero's own code does.

# Reachy Alive — Architecture

## Overview

Reachy Mini (Wireless) driven by a layered architecture: fast reflexes never block on slow AI. All compute runs on a laptop; the robot is reached over WiFi (streamed mode). Scaffolded with `reachy-mini-app-assistant` (default template), running as a `ReachyMiniApp` (`reachy_mini_app_api`) — connection, `stop_event`, and settings API are handled by the framework.

## Architecture

```
main.py (ReachyMiniApp.run(), ~50Hz loop, provided by framework)
        │
   Shared State  ←──────────────┬──────────────┬──────────────┐
   (lock-protected)              │              │              │
        │                        │              │              │
┌───────▼────────┐   ┌───────────▼──────┐  ┌────▼───────────┐ ┌▼─────────────────┐
│ brainstem       │   │ sensory_cortex   │  │ hippocampus    │ │ prefrontal_cortex │
│ (in run loop,   │   │ (own thread)     │  │  + amygdala    │ │ (own thread)      │
│  never blocks)  │   │                  │  │ (own thread)   │ │                   │
└─────────────────┘   └──────────────────┘  └────────────────┘ └───────────────────┘
```

Priority, high → low: **external target (fear/surprise/LLM) > discrete idle gesture > breathing (default)**.

## Modules

### `brainstem/` — only code that touches `ReachyMini`. Never blocks.
- `robot_manager.py` — the run loop itself. Purely mechanical: reads `current_animation_target`, sends it via `set_target`/`play_move`. No decisions.
- `idle_behaviors/idle_manager.py` — owns all idle arbitration: internal countdown + checks `last_external_command_at`. Calls `breathing.py` by default, or triggers a discrete gesture when its timer fires.
- `idle_behaviors/breathing.py` — pure function, continuous sine wave (head z-offset). No state.
- `idle_behaviors/base_behavior.py` — common interface (`trigger()`) for one-off gestures.
- `idle_behaviors/yawning.py`, `stretching.py`, `looking_around.py` — implement `base_behavior`. Yawn/stretch: `play_move` from the emotions library if it exists (check `list_moves()` first), else custom later. Look-around: procedural `goto_target` (sweep pattern).

### `sensory_cortex/` — perception only, no decisions.
- `vision.py` — MediaPipe (face/pose) + YOLOv8 (objects) → writes `perceived_objects`.
- `hearing.py` — Whisper (STT) + a lightweight amplitude-spike check (independent of Whisper) → writes `perceived_objects` / `sudden_noise_detected`.

### `hippocampus/` — memory.
- `database.py` — SQLite CRUD for encountered objects.
- `habituation.py` — novelty score (0–100, decays with repeated encounters).

### `amygdala/` — fast reactions, bypasses the LLM.
- `reactions.py` — rules: `novelty==100 → surprise`; `sudden_noise OR scary object (hardcoded list) → fear` (no habituation for fear). Writes `current_animation_target` + `last_external_command_at`. Calls `play_move(moves.get(...))` directly.

### `prefrontal_cortex/` — the only code that calls an LLM. Own thread, reads from a queue.
- `prompt_builder.py` — builds prompt from Shared State.
- `ai_client.py` — calls Ollama (local).
- `speech.py` — phase 1: trigger the move's built-in sound only. Phase 2+: gTTS for spoken words.

## Shared state

```python
class SharedState:
    lock: threading.Lock
    current_animation_target: str | None       # written by idle_manager / reactions / prefrontal
    last_external_command_at: float | None      # written by reactions / prefrontal only
    perceived_objects: list[str]                # written by vision/hearing
    sudden_noise_detected: float | None         # written by hearing
    novelty_score: int                          # written by habituation
    last_llm_utterance: str | None              # written by ai_client
```

## Tech stack

| Need | Choice | Note |
|---|---|---|
| Motor control | `reachy_mini` SDK (`ReachyMiniApp`, `set_target`/`goto_target`/`play_move`) | framework-managed connection |
| Emotions/idle content | `reachy-mini-emotions-library`, `reachy-mini-dances-library` | check `list_moves()` before assuming a name exists |
| LLM | Ollama, local | GPU contention with vision is the top risk — measure early; Jetson = future mitigation |
| Vision | MediaPipe + YOLOv8 | local, fast, no cloud VLM |
| STT | Whisper, local | + separate amplitude-spike check for startle |
| TTS | built-in move sounds (phase 1) → gTTS (phase 2+) | |
| Memory | SQLite | vector DB not needed yet |
| Concurrency | `threading` + lock + `queue` for LLM tasks | GIL is fine, everything here is I/O-bound |
| Connectivity | Wireless, streamed (compute on laptop) | |

## Roadmap

- [ ] 0. Scaffold app (`reachy-mini-app-assistant create`, default template)
- [ ] 1. `breathing.py` wired into the existing run loop — validate motion + WiFi latency
- [ ] 2. `idle_manager.py` + `base_behavior.py` + yawning/stretching/looking_around
- [ ] 3. `vision.py` — log detections only
- [ ] 4. `hippocampus/` — novelty score, no robot needed to test
- [ ] 5. `amygdala/reactions.py` — surprise + fear
- [ ] 6. `prefrontal_cortex/` in isolation (CLI, no robot)
- [ ] 7. Full integration, sound-only expression
- [ ] 8. Personality tuning
- [ ] Later: spoken TTS, custom moves, Jetson, config UI

## Key decisions (one-liners)

- Blackboard (Shared State) over ROS2: single machine, single robot — ROS2 solves a distribution problem we don't have.
- `threading` over `multiprocessing`/`asyncio`-only: everything here is I/O-bound (waits on ticks, camera frames, LLM calls), GIL releases during waits.
- Python app over JS/Web (SDK's own default): needs continuous local compute (vision, real-time loop, DB).
- Wireless streamed mode: compute stays on the laptop, WiFi replaces USB as transport.
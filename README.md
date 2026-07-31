---
title: Reachy Alive
emoji: 🧠
colorFrom: red
colorTo: blue
sdk: static
pinned: false
short_description: Autonomous, lifelike idle behavior for a Reachy Mini Wireless robot — breathing, stretching, yawning, and (soon) perception, memory, and reactions layered on top of a real-time control loop that never blocks.
tags:
 - reachy_mini
 - reachy_mini_python_app
---

# Reachy Alive

Autonomous, lifelike idle behavior for a Reachy Mini Wireless robot — breathing, stretching, yawning, and (soon) perception, memory, and reactions layered on top of a real-time control loop that never blocks.

Architecture rationale and design decisions live in [`plan.md`](./plan.md); this README covers current status and how to run things.

## Status

**Implemented:**
- Real-time control loop (`RobotManager`), decoupled from decision-making
- Idle arbitration (`IdleManager`): continuous breathing by default, discrete gestures at randomized intervals
- Three idle behaviors: `breathing` (continuous), `stretching` and `yawning` (hand-made, procedural)
- Shared `Move` interface for anything playable on the robot — library moves (`LibraryMove`) and hand-made gestures share the same `trigger()` contract
- Thread-safe `SharedState` blackboard for coordinating modules
- Unit tests (`pytest`) for all of the above, using a mocked robot — no hardware required
- `try_move.py` CLI for manually testing a single gesture on real hardware

**Not yet implemented:** perception, memory, reactions, and LLM-driven behavior (see Roadmap).

## Project structure

```
reachy_alive/
├── main.py                     # ReachyMiniApp entry point, framework wiring
├── shared_state.py             # Thread-safe blackboard shared across modules
├── move.py                     # Move interface: anything playable on the robot
├── library_move.py             # Move wrapper for named moves from the emotions library
│
├── brainstem/                  # Real-time control, never blocks
│   ├── robot_manager.py        # Control loop; only module that calls ReachyMini
│   ├── idle_manager.py         # Idle arbitration: breathing vs. discrete gestures
│   └── custom_idle_moves/
│       ├── breathing.py        # Continuous idle motion
│       ├── stretching.py       # Hand-made gesture
│       └── yawning.py          # Hand-made gesture
│
├── scripts/
│   └── try_move.py             # Manual, single-gesture testing on real hardware
│
└── tests/                      # Unit tests, hardware-independent
```

### Planned modules

| Module | Role |
|---|---|
| `sensory_cortex/` | Perception: vision (MediaPipe/YOLOv8) and hearing (Whisper + noise detection), writing to `SharedState` |
| `hippocampus/` | Episodic memory: SQLite-backed novelty scoring for encountered objects |
| `amygdala/` | Fast reflexes (surprise, fear) that bypass the LLM entirely for sub-100ms reactions |
| `prefrontal_cortex/` | LLM-driven deliberation (local, via Ollama) and expression |

## Getting started

Install the package in editable mode (required for `reachy_alive.*` imports to resolve consistently):
```bash
uv pip install -e .
```

Run the app (robot must be powered on and toggled ON in Reachy Mini Control):
```bash
python reachy_alive/main.py
```

Run the test suite (no hardware required):
```bash
pytest
```

Manually trigger a single gesture on real hardware:
```bash
python reachy_alive/scripts/try_move.py stretching
python reachy_alive/scripts/try_move.py yawning
python reachy_alive/scripts/try_move.py library boredom1
```

## Roadmap

1. Sensory Cortex — vision (MediaPipe/YOLOv8), logging detections only
2. Hippocampus — novelty scoring, testable without the robot
3. Amygdala — surprise and fear reflexes, reading `SharedState`
4. Prefrontal Cortex — local LLM (Ollama) integration, isolated and CLI-testable first
5. Full integration — non-verbal expression via built-in move sounds
6. Personality tuning; later: spoken TTS, custom recorded moves, dedicated Jetson for vision/LLM offload
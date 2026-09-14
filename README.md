---
title: Reachy Alive
emoji: 🧠
colorFrom: red
colorTo: blue
sdk: static
pinned: false
short_description: Autonomous, lifelike behavior for a Reachy Mini — breathing, stretching, yawning, and (soon) perception and reactions on top of a control loop that never blocks.
tags:
 - reachy_mini
 - reachy_mini_python_app
---

# Reachy Alive

Autonomous, lifelike behavior for a Reachy Mini — breathing, stretching, yawning, and (soon) perception, reactions, and deliberation, layered on top of a real-time control loop that never blocks.

Built as an extension platform: adding a behavior means dropping a file in the right folder. Architecture rationale lives in [`plan.md`](./plan.md); this README covers current status and how to run things.

## Status

**Implemented:**
- Real-time control loop (`RobotManager`), decoupled from decision-making
- Idle arbitration (`IdleManager`): continuous breathing by default, discrete gestures at randomized intervals
- Three idle behaviors: `breathing` (continuous), `stretching` and `yawning` (hand-made, procedural)
- Shared `Move` interface — library moves and hand-made gestures share the same `play()` contract, which always returns the robot to neutral after the move
- Thread-safe `SharedState` blackboard for coordinating modules
- Unit tests (`pytest`) with a mocked robot — no hardware required
- `try_move.py` CLI for manually testing a single gesture

**Not yet implemented:** perception, reflexes, memory, and LLM-driven behavior.

## Project structure

```
reachy_alive/
├── main.py # Entry point: builds and wires everything
├── shared_state.py # Thread-safe blackboard; one writer per field
├── robot_manager.py # Control loop; only module that calls ReachyMini
│
├── moves/
│ ├── base.py # Move interface + LibraryMove
│ ├── breathing.py # Continuous idle motion
│ ├── stretching.py # Hand-made gesture
│ └── yawning.py # Hand-made gesture
│
├── brainstem/
│ └── idle_manager.py # Picks between breathing and discrete gestures
│
├── assets/sounds/ # Audio used by hand-made gestures
├── scripts/try_move.py # Manual, single-gesture testing
└── tests/ # Hardware-independent unit tests
```

## Modules

| Module | Biological analogy | Role in the code |
|---|---|---|
| `brainstem/` | Automatic, unconscious regulation — breathing, reflexive posture | Arbitrates idle behavior: continuous breathing, occasional gestures. Runs every tick, never waits. **Implemented.** |
| `sensory_cortex/` | Turns raw signal into recognizable percepts | Camera, motion and face detection. Writes what it sees to `SharedState`, decides nothing. *Planned.* |
| `amygdala/` | Threat and novelty detection — reacts before the cortex has understood | Fast, local, synchronous reflexes. No network, no waiting. *Planned.* |
| `prefrontal_cortex/` | Deliberation, personality, choosing a considered response | Async cloud LLM call, with timeout and fallback. Never blocks the loop. *Planned.* |
| `hippocampus/` | Episodic memory — what happened, how often, how long ago | SQLite-backed novelty scoring. *Left as a good first issue for contributors.* |

A module's folder is decided by its **execution regime**, not by anatomy: fast, local, synchronous goes to `amygdala/`; slow, remote, asynchronous goes to `prefrontal_cortex/`. That way "which lobe does face detection belong to?" never has to be argued — the question is only whether the code can block.

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

Manually trigger a single gesture:
```bash
try-move stretching
try-move yawning
try-move library boredom1
```

## Roadmap

1. **Perception** — camera, motion and face detection, writing to `SharedState`. No reactions yet.
2. **Reflexes** — first fast reaction (startle). The robot perceives and responds.
3. **Deliberation** — async cloud LLM call, with timeout and fallback.
4. **Unified arbitration** — three decision-makers competing; migrate to a behavior tree.
5. **Packaging** — Hugging Face Space, one-click install, CI, contribution guide.
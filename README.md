---
title: Reachy Alive
emoji: 🧠
colorFrom: red
colorTo: blue
sdk: static
pinned: false
short_description: A Reachy Mini that feels alive, even when idle.
tags:
 - reachy_mini
---

# Reachy Alive

[![tests](https://github.com/HTurlet15/reachy_alive/actions/workflows/tests.yml/badge.svg)](https://github.com/HTurlet15/reachy_alive/actions/workflows/tests.yml)

Reachy Alive aims to turn a Reachy Mini into a real little desk companion.
It starts with a body that feels alive: the robot breathes, and every now
and then yawns, stretches, sneezes or hiccups — on its own, like a
creature, not on command. Perception, reactions and deliberation come
next, layered on a control loop that never blocks.

**Want to add a gesture?** See [CONTRIBUTING.md](./CONTRIBUTING.md).

## What the robot does today

- **Breathes** continuously while idle.
- **Plays a gesture** at random intervals, from three kinds of moves:
  - written in code: `yawning`, `stretching`;
  - recorded by hand in Marionette: `hiccup`;
  - mixed — recorded head, coded antennas: `sneezing`;
  - plus a selection of Pollen's own emotions.
- Returns to neutral after every gesture, so the next one starts from a
  known pose.

Not yet: perception, reflexes, deliberation, memory.

## The brain map

The code is organized like a nervous system. Folders are named after brain
regions, and code goes wherever its speed fits, as in the brain: a reflex
that must fire in milliseconds goes to `amygdala/`, a considered response
that can take seconds goes to `prefrontal_cortex/`. A face appearing can
trigger both — a startle, then a greeting — and they live in different
folders.

| Module | Biological analogy | Role in the code |
|---|---|---|
| `brainstem/` | Automatic regulation — breathing, posture | Idle behavior: continuous breathing, occasional gestures. **Implemented.** |
| `sensory_cortex/` | Turns raw signal into percepts | Camera, motion and face detection, written to `SharedState`. *Planned.* |
| `amygdala/` | Reacts before the cortex has understood | Fast, local, synchronous reflexes. *Planned.* |
| `prefrontal_cortex/` | Deliberation, personality | Async cloud LLM call, with timeout and fallback. *Planned.* |
| `hippocampus/` | Episodic memory | What happened, how often, how long ago. *Planned.* |

Why it's built this way, and what comes next:
[ARCHITECTURE.md](./ARCHITECTURE.md).

## Develop

You don't need a physical robot: everything runs in simulation. Setup is
detailed in [CONTRIBUTING.md](./CONTRIBUTING.md#set-up); in short:

```bash
uv sync                               # project environment, SDK, simulation
uv run reachy-mini-daemon --sim       # the simulated robot
uv run try-move sneezing              # play one gesture (2nd terminal)
uv run pytest                         # the test suite, no robot needed
```

Run the whole app on a robot (powered on, daemon toggled on in Reachy
Mini Control):

```bash
uv run python reachy_alive/main.py
```

## Project structure

```
reachy_alive/
├── main.py              # Builds and wires everything; lists the idle gestures
├── robot_manager.py     # Control loop; the only module that calls ReachyMini
├── shared_state.py      # Thread-safe blackboard; one writer per field
├── brainstem/
│   ├── breathing.py     # Continuous idle motion
│   └── idle_manager.py  # Breathing by default, a gesture now and then
├── moves/               # Discrete gestures, and the guides to write one
├── assets/sounds/       # Gesture sounds, with the presets that made them
├── scripts/             # try-move, sound composition
└── static/              # Web page served by the app
tests/                   # Hardware-independent tests, run by CI on every PR
```
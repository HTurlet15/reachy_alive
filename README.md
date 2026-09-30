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
 - reachy_mini_python_app
---

# Reachy Alive

[![tests](https://github.com/HTurlet15/reachy_alive/actions/workflows/tests.yml/badge.svg)](https://github.com/HTurlet15/reachy_alive/actions/workflows/tests.yml)

Reachy Alive aims to turn a Reachy Mini into a real little desk companion.
It starts with a body that feels alive: the robot breathes, and every now
and then yawns, stretches, sneezes or hiccups — on its own, like a
creature, not on command. Perception, reactions and deliberation come
next, layered on a control loop that never blocks.

**Want to add a move?** See [CONTRIBUTING.md](./CONTRIBUTING.md).

## Use it

In Reachy Mini Control, install Reachy Alive from the app store, then run
it. The robot starts breathing, and plays an idle move every 20 to 30
seconds.

While it runs, the app's page shows up next to Reachy Mini Control. From
there you can:

- **play any move on demand** — handy for a demo, or to try one without
  waiting for it;
- **set how long the robot waits between idle moves.** A new setting
  applies from the next idle move.

Volume and microphone are set in Reachy Mini Control itself.

## What the robot does today

- **Breathes** continuously while idle.
- **Plays an idle move** at random intervals, from three kinds of moves:
  - written in code: `yawning`, `stretching`;
  - recorded by hand in Marionette: `hiccup`;
  - mixed — recorded head, coded antennas: `sneezing`;
  - plus a selection of Pollen's own emotions.
- Returns to neutral after every move, so the next one starts from a
  known pose.

Not yet: perception, reflexes, deliberation, memory.

## The brain map

The code is organized like a nervous system. Folders are named after brain
regions, and code goes wherever its speed fits, as in the brain: a reflex
that must fire in milliseconds goes to `amygdala/`, a considered response
that can take seconds goes to `prefrontal_cortex/`. A face appearing can
trigger both — a startle, then a greeting — and they live in different
folders. The plumbing they share (`control/`, `shared_state.py`,
`routes.py`) takes plain names: the metaphor is kept for what has a
biological sense.

| Module | Biological analogy | Role in the code |
|---|---|---|
| `brainstem/` | Automatic regulation — breathing, posture | Idle behavior: continuous breathing, occasional idle moves. **Implemented.** |
| `sensory_cortex/` | Turns raw signal into percepts | Camera, motion and face detection, written to `SharedState`. *Planned.* |
| `amygdala/` | Reacts before the cortex has understood | Fast, local, synchronous reflexes. *Planned.* |
| `prefrontal_cortex/` | Deliberation, personality | Async cloud LLM call, with timeout and fallback. *Planned.* |
| `hippocampus/` | Episodic memory | What happened, how often, how long ago. *Planned.* |

How it all fits together, the code map and what comes next:
[ARCHITECTURE.md](./ARCHITECTURE.md).

## Develop

You don't need a physical robot: everything runs in simulation. Setup is
detailed in [CONTRIBUTING.md](./CONTRIBUTING.md#set-up); in short:

```bash
uv sync                               # project environment, SDK, simulation
uv run reachy-mini-daemon --sim       # the simulated robot
uv run try-move sneezing              # play one move (2nd terminal)
uv run pytest                         # the test suite, no robot needed
```

Run the whole app on a robot (powered on, daemon toggled on in Reachy
Mini Control):

```bash
uv run python reachy_alive/main.py
```

While the app runs, its page is at `http://localhost:8042`.
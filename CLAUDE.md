# Reachy Alive

An open-source Reachy Mini app that makes the robot feel alive: it breathes,
stretches, yawns, and — soon — perceives its surroundings and reacts.

Built as an **extension platform**, not a closed product. Adding a behavior
means dropping a file in the right folder.

## The core constraint

The robot must keep moving while it thinks. A cloud LLM call takes 1-3
seconds; written naively, the robot freezes and looks dead — the exact
opposite of the point. Every architectural decision follows from this.

## Four rules

1. **A module's folder is decided by its execution regime, not by anatomy.**
   Fast/local/synchronous → `amygdala/`. Slow/remote/async → `prefrontal_cortex/`.
2. **The cortex never blocks the loop.** LLM calls are async.
3. **One writer per field in `SharedState`.** Every field has an owning module;
   others only read.
4. **Dependencies are explicit, never global.** Anything with a side effect at
   construction time (network, file, hardware) is built in `main.py` and passed
   down. Never at module level — a plain import must not download anything.

## Layout

    reachy_alive/
    ├── main.py             # composition root: builds and wires everything
    ├── shared_state.py     # thread-safe blackboard
    ├── robot_manager.py    # control loop; ONLY module that calls ReachyMini
    ├── moves/base.py       # Move interface + LibraryMove
    ├── moves/*.py          # breathing, stretching, yawning
    ├── brainstem/          # idle_manager.py
    ├── assets/sounds/
    ├── scripts/try_move.py
    └── tests/

Planned: `sensory_cortex/` (perception), `amygdala/` (reflexes),
`prefrontal_cortex/` (deliberation), `hippocampus/` (memory — left as a
good first issue for contributors).

## Known debt — do NOT fix yet

`IdleManager.get_pose()` decides, executes (`behavior.trigger()`) AND signals
with a `None` sentinel.

Target: decision-makers return an intent, `RobotManager` is the only executor,
and gets renamed to `RobotController`.

**Scheduled for sprint C**, when a second decision-maker exists to validate the
design. Designing it now would be guesswork. If you notice this and want to fix
it, don't — say so and move on.

## Sprints

- A — structure refactor — **done**
- B — `sensory_cortex/`: camera, motion and face detection, writes to
  `SharedState`. No reactions. **← current**
- C — `amygdala/` + decision/execution split. Milestone: perceives and reacts.
- D — `prefrontal_cortex/`: async cloud LLM, API key, timeout, fallback.
- E — unified arbitration, migrate to a behavior tree.
- F — packaging: HF Space, one-click install, CI, contribution guide.

## Environment

- `uv`, not pip. Run tests with `uv run --active pytest` from `reachy_alive/`
  (never the parent dir — the neighbouring `reachy-conversation` project also
  contains a package named `reachy_alive`).
- No physical robot right now. Simulator:
  `env -u WAYLAND_DISPLAY GDK_BACKEND=x11 reachy-mini-daemon --sim`
  (the env vars work around a MuJoCo/GLFW bug on Wayland).
- Manual visual check: `try-move yawning`, `try-move stretching`,
  `try-move library boredom1`.
- `pytest` passing is not enough. Asset paths, real library loading and visual
  correctness only show up when actually running.

## SDK reference

The `reachy_mini` SDK is cloned locally at `../reachy_mini/`. Consult its
skills before writing motor or audio code — in particular
`docs/skills/motion-philosophy.md` and `docs/skills/control-loops.md`.

Key points already learned from them:
- `goto_target()` is the default (gestures, choreography). It cannot react to
  anything mid-interpolation.
- `set_target()` only inside a single control loop at 50-100 Hz. Multiple
  scattered `set_target()` calls is a documented anti-pattern — and is exactly
  the debt above.
- Use `time.monotonic()`, never `time.time()`.

## Accepted hardware limits

- Jitter on `set_target()` — upstream bug.
- `push_audio_sample()` broken on Wireless (pollen-robotics/reachy_mini#601) —
  gesture audio uses `.wav` files in `assets/sounds/` via `play_sound()`.

## Conventions

- Docstrings say what the code does; the *why* goes in the commit message.
  Google style (`Args:` / `Returns:`).
- Inline comments only when a line genuinely needs one. `TODO` only if
  actionable.
- Self-explanatory names. No abstraction without two real cases to justify it.
- Conventional Commits, frequent commits.
- Exactly **two** examples per behavior category — never a third. Two says
  "add another"; five says "it's finished".

## How to work with me

I'm learning, not just shipping. One brick at a time, never two new concepts at
once. Explain the *why* of a design choice before writing code.

Be a real senior:
- Contradict me when I'm wrong, with the reasoning.
- Say when you're unsure instead of asserting.
- If I reach for a trick where there's a design question, name it.
- Flag scope creep and over-engineering — that's my failure mode.
- Tell me when I switch from "understanding" mode to "results" mode.
# Reachy Alive

An open-source Reachy Mini app that makes the robot feel alive: it breathes,
stretches, yawns, hiccups... and — soon — perceives its surroundings and reacts.

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
    ├── interpolate.py      # interpolate(start, end, p)
    ├── moves/
    │   ├── base.py         # Move, PhasedMove, LibraryMove
    │   ├── yawning.py      # reference procedural move
    │   └── stretching.py
    ├── brainstem/
    │   ├── idle_manager.py
    │   └── breathing.py    # continuous pose function, not a Move
    ├── assets/sounds/      # grouped per move, .wav next to its jsfxr preset
    ├── scripts/try_move.py
    └── tests/              # mirrors the package layout

Planned: `sensory_cortex/` (perception), `amygdala/` (reflexes),
`prefrontal_cortex/` (deliberation), `hippocampus/` (memory — left as a
good first issue for contributors).

## The Move contract

Callers use `play()`, which uploads the move's sounds, runs `_perform()`,
then sends the robot to neutral in `RETURN_DURATION_S`.

A move may land on neutral as part of its own choreography, at its own tempo
(`yawning` and `stretching` do). `play()` returns there anyway, without
reading where the robot is — for a move that already landed there, it's a
no-op. The case that needs the net: recorded library moves end wherever their
recording ended.

**Three ways to write one:**

- `PhasedMove` — a sequence of phases, each timed by its own sound. Declare
  `PHASE_SOUNDS`, write `_pose_at(phase, p, step)` returning
  `(head_pose, [left_antenna, right_antenna])`. Everything else — durations
  read from the files, phase tracking, sound firing, `sound_paths()` — is
  inherited. This is the normal case.
- `Move` directly — implement `_perform()` and `sound_paths()`. For gestures
  that aren't phase-based, including mixed recorded/coded ones.
- `LibraryMove` — wraps a move from a Hugging Face dataset. No code at all.

See `moves/README.md` for the full guide, `assets/sounds/README.md` for the
jsfxr preset and sound packaging.

## Sound upload

On Wireless, `play_sound()` uploads the file over HTTP before playing it,
which freezes the gesture mid-motion. So `prepare()` uploads a move's sounds
ahead of time and maps each local path to its copy on the robot; `Move.play_sound()`
then plays the uploaded copy. `IdleManager` picks the next gesture in advance
and calls `prepare()` in a background thread while the robot is still
breathing, so nothing is uploaded during a gesture.

Moves must play sounds with `self.play_sound()`, never
`reachy_mini.media.play_sound()`, or the file is re-uploaded mid-gesture.

Known limit: even with the file already on the robot, the play command is an
HTTP round trip (~100-300 ms over Wi-Fi), so a sound starts slightly after its
phase. Accepted for now — running the app on the robot itself should remove it.

## Known debt — do NOT fix yet

`IdleManager.get_pose()` decides, executes (`behavior.play()`) AND signals
with a `None` sentinel. It also prepares the next gesture.

Target: decision-makers return an intent, `RobotManager` is the only executor,
and gets renamed to `RobotController`.

**Scheduled for sprint C**, when a second decision-maker exists to validate the
design. Designing it now would be guesswork. If you notice this and want to fix
it, don't — say so and move on.

## Sprints

- A — structure refactor — **done**
- **v1 release — current.** Five idle gestures, two contributor guides, then
  README, CONTRIBUTING, CI, HF Space. Ships before sprint B so people can start
  contributing gestures while perception is built.
- B — `sensory_cortex/`: camera, motion and face detection, writing to
  `SharedState`. Also the mechanism to aim the head at a point — but nothing
  calls it yet. **No new behavior: the robot still just breathes.**
- C — `amygdala/` + decision/execution split. Innate reflexes only: a sudden
  noise, a face appearing, movement where there was none. No memory, no
  judgement. **Milestone: the robot perceives and reacts.**
- D — `prefrontal_cortex/`: async cloud LLM, API key, timeout, fallback. This
  is what decides to *look at* someone, rather than reflexively startle.
- E — unified arbitration, migrate to a behavior tree.
- F — packaging leftovers and polish.

Later, not scheduled: `hippocampus/` conditioning — the cortex writes what it
judged ("cat = curious, not dangerous"), the amygdala reads it back in
milliseconds and reacts appropriately without reasoning. The robot learns: its
fast reaction becomes right because it was slow once.

## Design decisions not to re-litigate

- **The robot does not follow faces around.** Tracking a face is a mechanism,
  not a behavior. It runs when a decision-maker asks for it — because it was
  called, or because the cortex decided to look. A robot that tracks everyone
  by default reads as a security camera, not a creature.
- **Gaze is continuous, not a gesture.** When it lands, it should layer over
  breathing rather than replace it — the primary/secondary split in Pollen's
  motion docs. Not decided yet; revisit when a decision-maker actually wants it.

## Environment

- `uv`, not pip. Run `pytest` from the repo root — never the parent dir, where
  the neighbouring `reachy-conversation` project also contains a package named
  `reachy_alive`.
- Robot: Reachy Mini **Wireless**, on Wi-Fi. It boots with torque disabled;
  motion commands are then accepted but silently ignored
  (pollen-robotics/reachy_mini#1306).
- Simulator: `env -u WAYLAND_DISPLAY GDK_BACKEND=x11 reachy-mini-daemon --sim`
  (the env vars work around a MuJoCo/GLFW bug on Wayland). The simulator never
  exercises the upload path — its audio backend reads files directly.
- Recorded moves are cached locally. A move added to a dataset after its first
  download is invisible until the cache is cleared:
  `rm -rf ~/.cache/huggingface/hub/datasets--<user>--<dataset>`.
- Manual visual check: `try-move yawning`, `try-move stretching`,
  `try-move recorded hiccup-full`, `try-move pollen boredom1`.
- `pytest` passing is not enough. Asset paths, real library loading, sound
  upload and visual correctness only show up when actually running.
- Robot logs: `ssh pollen@<ip>` (password `root`), then
  `journalctl -u reachy-mini-daemon -f`. Get the IP with
  `mini.client.get_status().wlan_ip`.
- Robot state before debugging: `mini.client.get_status().backend_status` —
  `motor_control_mode`, `nb_error`, `error`.

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
- `enable_motors()` pins targets to the present pose, so call it before any
  `set_target`.
- Use `time.monotonic()`, never `time.time()`.

## Accepted hardware limits

- **Streaming `set_target` from a far pose can take the daemon down.** It
  doesn't interpolate, so from the sleep pose it asks for a huge instant jump;
  the daemon restarts (`1012`) or the serial link to the motors retries.
  `try-move` eases into neutral with `goto_target` first.
- **Head below z = -170 mm wedges the IK solver permanently** — commands and
  sounds keep being accepted, nothing moves, until the daemon restarts. The
  recorded moves `waiting`, `mini-deep-sleep` and `toc-toc-toc` do this
  (pollen-robotics/reachy_mini#1417).
- **Antennas jitter at exactly vertical** — neutral is `NEUTRAL_ANTENNAS_RAD`
  (~10° off), not `[0.0, 0.0]`.
- Jitter on `set_target()` — upstream bug.
- `push_audio_sample()` broken on Wireless (pollen-robotics/reachy_mini#601) —
  gesture audio uses `.wav` files in `assets/sounds/` via `play_sound()`.
- SDK and daemon versions must match. A mismatch gives no clear error — the
  robot just fails on the first recent feature used. Check with
  `uv pip show reachy-mini` and `mini.client.get_status().version`.

## Conventions

- Docstrings say what the code does; the *why* goes in the commit message.
  Google style (`Args:` / `Returns:`).
- Inline comments only when a line genuinely needs one. `TODO` only if
  actionable.
- Self-explanatory names. No abstraction without two real cases to justify it.
- Conventional Commits, frequent commits.
- One or two examples per creation method — never more. Two says "add another";
  five says "it's finished".

## How to work with me

I'm learning, not just shipping. One brick at a time, never two new concepts at
once. Explain the *why* of a design choice before writing code.

Be a real senior:
- Contradict me when I'm wrong, with the reasoning.
- Say when you're unsure instead of asserting.
- If I reach for a trick where there's a design question, name it.
- Flag scope creep and over-engineering — that's my failure mode.
- Tell me when I switch from "understanding" mode to "results" mode.
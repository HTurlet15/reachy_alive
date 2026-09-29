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
    ├── shared_state.py     # thread-safe blackboard: facts, not orders
    ├── commands.py         # commands decision-makers hand to RobotController
    ├── action_selector.py  # chooses one proposal per tick (future behavior tree)
    ├── robot_controller.py # control loop; executes commands
    ├── interpolate.py      # interpolate(start, end, p)
    ├── moves/
    │   ├── base.py         # Move, PhasedMove, LibraryMove
    │   ├── yawning.py      # reference procedural move
    │   ├── stretching.py
    │   └── sneezing.py     # reference mixed move
    ├── brainstem/
    │   ├── idle_manager.py
    │   └── breathing.py    # continuous pose function, not a Move
    ├── static/             # settings page: plays any move on demand
    ├── assets/sounds/      # grouped per move, .wav next to its jsfxr preset
    ├── scripts/try_move.py
    └── tests/              # mirrors the package layout

Planned: `sensory_cortex/` (perception), `amygdala/` (reflexes),
`prefrontal_cortex/` (deliberation), `hippocampus/` (memory — left as a
good first issue for contributors).

## Execution model

`RobotController` owns the control loop. It makes no decisions: each tick, it
asks for a command (`commands.py`) and executes it. Decision-makers never
drive the robot. Moves do talk to the robot, but only while `RobotController`
executes a `PlayMove`, from the loop's thread. It also records in
`SharedState` when a move ends, whoever asked for it: it is the only module
that knows for sure.

State and orders travel separately. `SharedState` holds facts any module can
read at any time. A command is an order: handed to `RobotController`, executed
once.

Decision-makers propose; `ActionSelector` chooses one proposal per tick.
A move requested from the settings page (`POST /moves/{name}/play`, queued)
wins over idle, and only the latest request plays. The idle manager isn't
consulted while it loses, only told (`interrupt()`).

## The Move contract

Callers use `play()`, which uploads the move's sounds, runs the gesture,
then sends the robot to neutral in `RETURN_DURATION_S`.

A move may land on neutral as part of its own choreography, at its own tempo
(`yawning` and `stretching` do). `play()` returns there anyway, without
reading where the robot is — for a move that already landed there, it's a
no-op. The case that needs the net: recorded library moves end wherever their
recording ended.

**Two ways to write one:**

- `PhasedMove` — a sequence of phases, each timed by its own sound. Declare
  `PHASE_SOUNDS` (plus `SILENT_PHASE_DURATIONS_S` and `PHASE_PADDING_S` when
  needed), and write `_pose_at(phase, p, elapsed_s)` returning
  `(head_pose, [left_antenna, right_antenna], body_yaw)`. It computes a pose
  and never talks to the robot. Rhythms are in seconds (`alternating_sign`),
  never in ticks. Anything that varies between plays goes in `_on_start()`.
  Coded and mixed moves both use it.
- `LibraryMove` — wraps a move from a Hugging Face dataset (Pollen's library
  or a Marionette recording). No code at all.

Never subclass `Move` directly: `_perform` is the internal loop and will
change when gestures run tick by tick. A test fails if a move in `moves/`
defines `_perform`.

A move's `name` is its identifier, in logs and in the settings page routes:
lowercase words joined by hyphens. Coded moves derive it from their class
name (`DeepBreath` → `deep-breath`), recorded moves from their recording.

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

A move requested from the settings page isn't prepared ahead: `play()`
uploads its sounds just before it starts, which can add a short pause on
Wireless.

## Known debt — do NOT fix yet

`Move.play()` blocks the control loop for the whole gesture. So a gesture
can't be interrupted, `PlayMove` exists, and moves still talk to the robot
during `play()`.

Target: gestures return a pose each tick, and `PlayMove` goes away.
**Scheduled for sprint C**, with reflexes, which need interruption anyway.
If you notice this and want to fix it, don't — say so and move on.

The decision/execution split itself is done: decision-makers return commands
(`commands.py`), `RobotController` executes them. It came earlier than planned
because moves requested from the settings page are a second decision-maker.

## Sprints

- **A — v1 release — current.** Structure refactor (done), idle gestures of
  all three kinds (coded, Marionette, mixed), a stable Move contract,
  contributor guides, README, CONTRIBUTING, CI, HF Space, settings page that
  plays any move on demand. **Ends once the app is published and the promo
  video is out**, so people can start contributing gestures while perception
  is built.
- B — `sensory_cortex/`: camera, motion and face detection, writing to
  `SharedState`. Also the mechanism to aim the head at a point — but nothing
  calls it yet. **No new behavior: the robot still just breathes.**
- C — `amygdala/` + gestures that run tick by tick. Innate reflexes only: a
  sudden noise, a face appearing, movement where there was none. No memory,
  no judgement. **Milestone: the robot perceives and reacts.**
- D — `prefrontal_cortex/`: async cloud LLM, API key, timeout, fallback. This
  is what decides to *look at* someone, rather than reflexively startle.
- E — unified arbitration, migrate the `ActionSelector` to a behavior tree.
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
- **Volume and microphone stay in Reachy Mini Control.** They are robot-wide
  settings the daemon persists across apps; the app never changes them.
- **One word: "move".** Code, routes and docs say "move", like the SDK.
  "Gesture" is being phased out (idle code still uses it until its rename
  to "idle move").

## Environment

- `uv`, not pip. Run `pytest` from the repo root — never the parent dir, where
  the neighbouring `reachy-conversation` project also contains a package named
  `reachy_alive`.
- Robot: Reachy Mini **Wireless**, on Wi-Fi. It boots with torque disabled;
  motion commands are then accepted but silently ignored
  (pollen-robotics/reachy_mini#1306).
- Simulator: `env -u WAYLAND_DISPLAY GDK_BACKEND=x11 reachy-mini-daemon --sim`
  (the env vars work around a MuJoCo/GLFW bug on Wayland). The simulator never
  exercises the upload path — its audio backend reads files directly. If it
  fails with `Address already in use`, another daemon is running: find it with
  `ss -ltnp | grep -E ':8000|:8443'`.
- Recorded moves are cached locally. A move added to a dataset after its first
  download is invisible until the cache is cleared:
  `rm -rf ~/.cache/huggingface/hub/datasets--<user>--<dataset>`.
- Manual visual check: `try-move yawning`, `try-move stretching`,
  `try-move recorded hiccup-full`, `try-move pollen boredom1`.
- Settings page: `http://localhost:8042` while the app runs. Routes can be
  tried with `curl -i -X POST http://localhost:8042/moves/<name>/play`.
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
  scattered `set_target()` calls is a documented anti-pattern — `set_target()`
  now lives in `RobotController`, plus `PhasedMove._perform` until gestures run
  tick by tick.
- `enable_motors()` pins targets to the present pose, so call it before any
  `set_target`.
- Use `time.monotonic()`, never `time.time()`.

## Accepted hardware limits

- **Robot inert while the daemon reports healthy.** The motor controller
  retries reads but not writes, and silently drops write errors: a transient
  serial error can lose the torque-enable order. The daemon then reports
  `enabled` and `nb_error: 0`, accepts every command, and nothing moves. The
  marker is `Serial I/O recovered after N retries` in the journal. Only
  `sudo systemctl restart reachy-mini-daemon` recovers —
  `POST /api/daemon/restart` isn't enough
  (pollen-robotics/reachy-mini-motor-controller#47; see also
  pollen-robotics/reachy_mini#1306, #1417, #1430).
- **Ease into neutral before streaming.** `set_target` doesn't interpolate, so
  from the sleep pose it asks for a huge instant jump. Entry points (and
  `try-move`) ease into neutral with `goto_target` first. It reduces motor
  strain but doesn't prevent the issue above.
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
- Docstrings and comments in English, always.
- Inline comments only when a line genuinely needs one. `TODO` only if
  actionable.
- Self-explanatory names. No abstraction without two real cases to justify it.
- Conventional Commits, frequent commits.
- One or two examples per creation method — never more. Two says "add another";
  five says "it's finished".
- Before any refactor, reread ARCHITECTURE.md and this file: they hold the
  decisions not to re-litigate and the debt not to fix yet.

## How to work with me

I'm learning, not just shipping. One brick at a time, never two new concepts at
once. Explain the *why* of a design choice before writing code.

Be a real senior:
- Contradict me when I'm wrong, with the reasoning.
- Say when you're unsure instead of asserting.
- If I reach for a trick where there's a design question, name it.
- Flag scope creep and over-engineering — that's my failure mode.
- Tell me when I switch from "understanding" mode to "results" mode.
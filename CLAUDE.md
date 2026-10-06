# Reachy Alive — notes for Claude

An open-source Reachy Mini app that makes the robot feel alive: it breathes,
plays idle moves, and will perceive and react.

**Read first:** [ARCHITECTURE.md](./ARCHITECTURE.md) for how the code is
organized, its rules, its code map and its roadmap;
[reachy_alive/moves/README.md](./reachy_alive/moves/README.md) for the Move
contract and how moves are written. This file only holds what those don't:
what not to touch, the internals, the environment, and how to work with me.

## Current sprint

**B — senses.** It ends once the four senses (inertial unit, touch, hearing,
vision) write their facts to `SharedState` and show on the app's page; the
robot still only breathes. Sprint letters follow the order of the roadmap in
ARCHITECTURE.md: A (v1), B (senses), C (interruptible body), D (reflexes),
E (deliberation), F (arbitration).

## Known debt — do NOT fix yet

Playing a move blocks the control loop for the whole move: a move can't be
interrupted, `PlayMove` exists, and moves still talk to the robot while they
play. Target: moves return a pose each tick and `PlayMove` goes away.
**Scheduled for sprint C**, with reflexes, which need interruption anyway.
If you notice this and want to fix it, don't — say so and move on.

## Design decisions not to re-litigate

- **The robot does not follow faces around.** Tracking a face is a mechanism,
  not a behavior. It runs when a decision-maker asks for it. A robot that
  tracks everyone by default reads as a security camera, not a creature.
- **Gaze is continuous, not a move.** When it lands, it should layer over
  breathing rather than replace it — the primary/secondary split in Pollen's
  motion docs. Not decided yet; revisit when a decision-maker wants it.
- **Volume and microphone stay in Reachy Mini Control.** They are robot-wide
  settings the daemon persists across apps; the app never changes them.
- **One word: "move".** Code, routes and docs say "move", like the SDK; idle
  code says "idle move".
- **Brain regions live in `brain/`; plumbing stays at the package root.**
  No `MixedMove` base class until a second mixed move.
- **A new idle move interval applies from the next idle move**, not
  immediately: the delay already drawn still runs.

## Internals the docs don't cover

- **Sound upload.** On Wireless, playing a local file uploads it over HTTP
  first, freezing the move. `Move.prepare()` uploads a move's sounds ahead
  and maps each local path to its copy on the robot; `Move.play_sound()`
  plays that copy. Moves must use `self.play_sound()`, never
  `reachy_mini.media.play_sound()`. `IdleManager` prepares the next idle move
  in a background thread while the robot breathes. Uploads are keyed by file
  name, so every play re-uploads. A move requested from the app's page isn't
  prepared ahead: short pause on Wireless.
- **Startup order.** The SDK starts the web server, then connects to the
  robot, then calls `run()`, where the routes are registered. The app's page
  is served before its routes exist, so it retries `GET /moves` (like
  `untilReady` in Pollen's conversation app).
- **Who writes `SharedState`.** `last_activity_at`: `RobotController`, when
  a move ends. The idle move interval: the routes only. `move_playing`: 
  `RobotController`, around each move it plays.
- **Logging.** In SDK 1.11 only the daemon configures logging. `main.py`'s
  `__main__` block calls `basicConfig` (no `force`) and sets the
  `reachy_alive` logger to INFO; Reachy Mini Control never runs that block.
  Don't override other libraries' logging config.
- **Launcher logs.** Reachy Mini Control labels anything on stderr as ERROR,
  including uv's "Using Python … environment" lines. Not an error.

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
- The app's page: `http://localhost:8042` while the app runs. Routes can be
  tried with `curl`, e.g. `curl -i -X POST http://localhost:8042/moves/<name>/play`.
- `pytest` passing is not enough. Asset paths, real library loading, sound
  upload and visual correctness only show up when actually running.
- Robot logs: `ssh pollen@<ip>` (password `root`), then
  `journalctl -u reachy-mini-daemon -f`. Get the IP with
  `mini.client.get_status().wlan_ip`.
- Robot state before debugging: `mini.client.get_status().backend_status` —
  `motor_control_mode`, `nb_error`, `error`.

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
  move audio uses `.wav` files in `assets/sounds/` via `play_sound()`.
- On Wireless, the play command is an HTTP round trip (~100-300 ms), so a
  sound may start slightly after its phase. Accepted; not observed as a
  problem so far.
- SDK and daemon versions must match. A mismatch gives no clear error — the
  robot just fails on the first recent feature used. Check with
  `uv pip show reachy-mini` and `mini.client.get_status().version`.

## SDK reference

The `reachy_mini` SDK is cloned locally at `../reachy_mini/`. Consult its
skills before writing motor or audio code — in particular
`docs/skills/motion-philosophy.md` and `docs/skills/control-loops.md`.

Key points already learned from them:
- `goto_target()` is the default (moves, choreography). It cannot react to
  anything mid-interpolation.
- `set_target()` only inside a single control loop at 50-100 Hz. Multiple
  scattered `set_target()` calls is a documented anti-pattern — `set_target()`
  lives in `RobotController`, plus `PhasedMove._perform` until moves run
  tick by tick.
- `enable_motors()` pins targets to the present pose, so call it before any
  `set_target`.
- Use `time.monotonic()`, never `time.time()`.

## Conventions

- Docstrings say what the code does; the *why* goes in the commit message.
  Google style (`Args:` / `Returns:`).
- Docstrings and comments in English, always.
- Inline comments only when a line genuinely needs one. `TODO` only if
  actionable.
- Self-explanatory names. No abstraction without two real cases to justify it.
- Conventional Commits, frequent commits, one short branch per topic.
- One or two examples per creation method — never more. Two says "add another";
  five says "it's finished".
- Docs change in the same PR as the code they describe. ARCHITECTURE.md holds
  the only code map and the only roadmap: update them there, never copy them.
- Before any refactor, reread ARCHITECTURE.md and this file: they hold the
  decisions not to re-litigate and the debt not to fix yet.
- No comment repeating the file's path at the top: the path already shows
  everywhere, and the comment goes stale on the first move.

## How to work with me

I'm learning, not just shipping. One brick at a time, never two new concepts at
once. Explain the *why* of a design choice before writing code.

Be a real senior:
- Contradict me when I'm wrong, with the reasoning.
- Say when you're unsure instead of asserting.
- If I reach for a trick where there's a design question, name it.
- Flag scope creep and over-engineering — that's my failure mode.
- Tell me when I switch from "understanding" mode to "results" mode.
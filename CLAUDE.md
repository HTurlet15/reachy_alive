# Reachy Alive — notes for Claude

An open-source Reachy Mini app that makes the robot feel alive: it breathes,
plays idle moves, perceives, and will react.

**Read first:** [ARCHITECTURE.md](./ARCHITECTURE.md) for how the code is
organized, its rules, its code map and its roadmap;
[reachy_alive/moves/README.md](./reachy_alive/moves/README.md) for the Move
contract and how moves are written;
[reachy_alive/brain/sensory_cortex/README.md](./reachy_alive/brain/sensory_cortex/README.md)
for how senses, features and detectors fit, and how detectors are written.
This file only holds what those don't:
what not to touch, the internals, the environment, and how to work with me.

## Current sprint

**C — interruptible body, released in v1.2.0.** Moves run tick by tick:
the `ActionSelector` cuts each one into a pose per tick, the
`RobotController` sends every pose, and its `SoundPlayer` starts the sounds;
nothing new shows on the robot. Next: D, reflexes, then gaze layered over
breathing (C/2). Sprint letters follow the order of the roadmap in
ARCHITECTURE.md: A (v1), B (senses), C (interruptible body), D (reflexes),
E (deliberation), F (arbitration).

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
- **A fact enters `SharedState` only with a planned reaction that uses it.**
  Raw signal (images, sound) never does: it stays inside its sense.
- **Moves are registered by hand; detectors are found in their sense's
  folder.** A move drives the robot, a detector only records facts.
- **Habituation belongs to the reflexes, not the detectors.** A detector
  says what happened; a reflex decides whether it's worth reacting to. It
  moves out of `SuddenNoiseDetector` in sprint D.
- **`SuddenNoiseDetector.START_THRESHOLD_DB` stays at 30 dB.** Checked on
  recordings (quiet room, TV, speech; `spike/senses`, `spike/NOTES.md`): no
  threshold separates a clap from a TV scene change or a first word.

## Internals the docs don't cover

- **Sound upload.** When the app runs on a laptop against the Wireless robot
  (WebRTC backend), playing a local file uploads it over HTTP first, freezing
  the move. On the robot itself, the local backend has no `upload_sound` and
  reads files from disk. So the app makes every sound playable once, at
  startup: `upload_sounds()` (`moves/robot_sounds.py`) returns a table from
  each local path to what `play_sound()` takes, and the `SoundPlayer`
  (`control/sound_player.py`) holds it. `play_sound()` returns only once the
  sound has started (20 to 45 ms on the robot, 55 to 85 ms from a laptop,
  #82): the `SoundPlayer` calls it from its own thread, never the loop. Moves never upload: they only list their `sound_cues`. The daemon
  keeps uploads in `/tmp/reachy_mini_sounds/`, by file name alone, until it
  restarts (its `routers/media.py`, SDK 1.13): no two moves may share a sound
  file name (a test checks it). A failed upload stops the app at startup.
- **Startup order.** The SDK starts the web server, then connects to the
  robot, then calls `run()`, where the routes are registered. The app's page
  is served before its routes exist, so it retries `GET /moves` (like
  `untilReady` in Pollen's conversation app).
- **Who writes `SharedState`.** Each fact has one writer:
  - `RobotController`: when the last move ended (as a move ends),
    `move_playing` (around each move, and while the robot
    wakes up), `commanded_pose` (each pose it sends);
  - each sense's facts, its detectors: bumps `BumpDetector`, antenna pushes
    `AntennaPushDetector`, sudden noises `SuddenNoiseDetector`, faces
    `FacePresenceDetector`;
  - the routes only: the idle move interval, and the senses switched off.
- **Hearing never stops recording.** Over WebRTC, the SDK's
  `stop_recording()` does nothing (pollen-robotics/reachy_mini#1508), so
  `HearingSense` starts recording at its first reading and never stops. A gap
  of more than 0.5 s between readings means the page switched hearing off:
  the sound queued meanwhile is dropped, or it would read as a sudden noise.
- **Logging.** In SDK 1.11 to 1.13, only the daemon configures logging. `main.py`'s
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
- The app's page: `http://localhost:8042` while the app runs, or
  `http://reachy-mini.local:8042` when it runs on the robot. Routes can be
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
  lives in `RobotController` only.
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
  decisions not to re-litigate.
- No comment repeating the file's path at the top: the path already shows
  everywhere, and the comment goes stale on the first move.
- Name what a condition checks: `head_still_rings = ...`, then
  `if strays_from_gravity and not head_still_rings:`. Keep methods that
  answer (`would_turn_on`, `is_expected`) apart from methods that change
  (`update`, `remember`).

## How to work with me

I'm learning, not just shipping. One brick at a time, never two new concepts at
once. Explain the *why* of a design choice before writing code.

Be a real senior:
- Contradict me when I'm wrong, with the reasoning.
- Say when you're unsure instead of asserting.
- If I reach for a trick where there's a design question, name it.
- Flag scope creep and over-engineering — that's my failure mode.
- Tell me when I switch from "understanding" mode to "results" mode.
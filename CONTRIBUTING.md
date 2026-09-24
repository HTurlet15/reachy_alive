# Contributing to Reachy Alive

Thanks for your interest! Reachy Alive aims to turn a Reachy Mini into a
real little desk companion. This page explains what we accept, how to set
up, and how to propose your work.

## What we accept for now: idle moves

A companion starts with a body that feels alive, so that's where we
begin. An **idle move** is something you do without noticing: a yawn, a stretch,
a sneeze, a hiccup. Nobody decides to hiccup. These gestures come on their
own, at random, and that's exactly what makes a creature look alive
rather than programmed. In the code, they live in the robot's
`brainstem`, the part that runs without thinking.

So a good idle move is:

- **involuntary**: something the robot does, not something it chooses
  to do (waving hello is not an idle move);
- **self-contained**: it starts and ends at rest, and doesn't react to
  anything around it;
- **short**: a few seconds, so it punctuates the robot's idle time
  without taking it over.

Seeing, listening and deciding (computer vision, reactions to people,
the rest of the intelligence) will come in later versions. Bug fixes are
welcome anytime.

## Set up

You don't need a physical robot: everything runs in simulation.

1. Install [uv](https://docs.astral.sh/uv/getting-started/installation/),
   which manages the project's Python and dependencies.
2. On Linux, install the system requirements listed in Pollen's
   [installation guide](https://huggingface.co/docs/reachy_mini/SDK/installation)
   (GStreamer). The Python side is handled by the next step.
3. Clone this repository and, from its folder, run:

   ```bash
   uv sync
   ```

   This creates a `.venv/` for the project, with the app, the Reachy Mini
   SDK, the MuJoCo simulation and pytest. There's nothing to activate:
   prefix commands with `uv run`, and they run in that environment.

4. Start the simulated robot, then play a move from a second terminal:

   ```bash
   uv run reachy-mini-daemon --sim
   uv run try-move yawning
   ```

> **The simulation crashes on start under Linux?** If you're in a Wayland
> session, it's likely a MuJoCo/GLFW bug
> ([google-deepmind/mujoco#1693](https://github.com/google-deepmind/mujoco/issues/1693)),
> not a Reachy Mini one. Forcing X11 works around it:
>
> ```bash
> env -u WAYLAND_DISPLAY GDK_BACKEND=x11 uv run reachy-mini-daemon --sim
> ```

> **Testing on a real robot?** The SDK version is pinned in
> `pyproject.toml` to match the robot's daemon. If your robot runs another
> version, update it first: a mismatch can crash the daemon without a
> clear error.

## Make your move

Everything is in [`reachy_alive/moves/README.md`](reachy_alive/moves/README.md):
planning the gesture, choosing between code, Marionette or both, making
its sound, and trying it. Each method has an example to copy.

**Keep the robot's voice.** Pollen's own sounds were made with a slide
whistle, and every sound here stays in that family: a round, sustained
tone that glides. Start from the shared preset, as explained in
[`reachy_alive/assets/sounds/README.md`](reachy_alive/assets/sounds/README.md),
so your move sounds like the same robot as the others.

## If your move uses a Marionette recording

Record it in your own Hugging Face dataset, and give the dataset and move
names in your pull request. Before merging, the maintainer copies the
recording into the project's dataset, `HTurlet15/reachy-alive`.

`main.py` only ever loads recordings from the project's dataset — never
from a contributor's. That way, the app doesn't break if a personal
dataset is renamed, made private or deleted.

## Before opening a pull request

- [ ] `uv run pytest` passes.
- [ ] The move plays with `uv run try-move`, in simulation or on a robot.
- [ ] Every sound starts from `base.jsfxr.json` and stays in the
      slide-whistle family.
- [ ] Every `.wav` is committed next to the `.jsfxr.json` preset that
      produced it.
- [ ] The move is registered in `main.py`, `reachy_alive/scripts/try_move.py`
      and, if it's a `PhasedMove`, `tests/moves/test_pose_contract.py`.
- [ ] Mixed move: `compose.py` and `PHASE_PADDING_S` match, and each
      has a comment pointing to the other.
- [ ] The head never goes below z = -170 mm.

## The pull request

- **One move per pull request.**
- **Attach a short video** of the move, in simulation or on the robot.
  Code review can't tell whether a gesture looks alive; a video can.
- **Commits** follow [Conventional Commits](https://www.conventionalcommits.org):
  `feat(moves): add sneezing`, `fix(moves): ...`, `docs: ...`.
- **Docstrings** say *what* the code does, in Google style. The *why*
  of a design choice goes in the commit message.
## What this changes

<!-- One or two sentences. For a new move: what the gesture is, and how it's built (code, Marionette or mixed). -->

## Video

<!-- New or changed move: drag a short video here, in simulation or on the robot. Code review can't tell whether a gesture looks alive. -->

## Checklist for a move

<!-- Not a move? Delete this section. -->

- [ ] `uv run pytest` passes.
- [ ] The move plays with `uv run try-move`, in simulation or on a robot.
- [ ] It's involuntary, starts and ends at rest, and lasts a few seconds.
- [ ] Every sound starts from `base.jsfxr.json` and stays in the slide-whistle family.
- [ ] Every `.wav` is committed next to the `.jsfxr.json` preset that produced it.
- [ ] The move is registered in `main.py`, `reachy_alive/scripts/try_move.py` and, if it's a `PhasedMove`, `tests/moves/test_pose_contract.py`.
- [ ] Mixed move: `compose.py` and `PHASE_PADDING_S` match, and each has a comment pointing to the other.
- [ ] Marionette recording: the dataset and move names are given above, so the maintainer can copy it into the project's dataset.
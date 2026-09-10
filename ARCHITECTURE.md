# Architecture

Why the code is organized this way. For what the project does and how to
run it, see the [README](./README.md).

## The core constraint

The robot must keep moving while it thinks. A cloud LLM call takes 1-3
seconds; written naively, the robot freezes and looks dead — the exact
opposite of the point. Every decision below follows from this.

## Four rules

**1. A module's folder is decided by its execution regime, not by anatomy.**
Fast, local, synchronous goes to `amygdala/`. Slow, remote, asynchronous
goes to `prefrontal_cortex/`. This avoids arguing about which lobe face
detection belongs to, and it maps to a real engineering boundary.

**2. The cortex never blocks the loop.**
LLM calls are async. The control loop keeps running while a request is in
flight.

**3. One writer per field in `SharedState`.**
A blackboard is the right fit for a single process with a few threads, but
it degenerates when anyone can write anywhere. Every field has an owning
module; the others only read.

**4. Dependencies are explicit, never global.**
`RecordedMoves` is injected into `LibraryMove` rather than built at module
level — otherwise a plain import downloads the library, including during
tests. Anything with a side effect at construction time is built in
`main.py` and passed down.

## Execution model

`main.py` is the composition root: it builds every object and wires them
together, once, at startup.

`RobotManager` owns the control loop. It is the only module that calls
`ReachyMini`. It makes no decisions — it asks a decision-maker what to do
and executes the answer.

Decision-makers (`IdleManager` today; reflexes and deliberation later) are
plain objects, testable without a robot.

## Known debt

`IdleManager.get_pose()` decides, executes (`behavior.trigger()`) **and**
signals with a `None` sentinel. The execution path is locked inside idle
behavior, which will get in the way once a second decision-maker exists.

Target: decision-makers return an intent, `RobotManager` is the only
executor. Scheduled for sprint C, when a second decision-maker exists to
validate the design — designing it cold would be guesswork.

## Accepted hardware limits

- Jitter on `set_target()` — upstream bug, not fixable from here.
- `push_audio_sample()` is broken on Wireless
  ([#601](https://github.com/pollen-robotics/reachy_mini/issues/601)),
  so gesture audio uses pre-generated `.wav` files in `assets/sounds/`
  played through `play_sound()` instead of streamed samples.

## Sprints

| | Scope | Estimate |
|---|---|---|
| A | Structure refactor: `moves/` at root, `RobotManager` lifted out of `brainstem/`, `RecordedMoves` injected | 4-6h — **done** |
| B | `sensory_cortex/`: camera, motion and face detection, writing to `SharedState`. No reactions. | 14-20h |
| C | `amygdala/` + the decision/execution split. First reflex. **Milestone: the robot perceives and reacts.** | 12-16h |
| D | `prefrontal_cortex/`: async cloud call, API key, timeout, fallback | 14-20h |
| E | Unified arbitration: three decision-makers competing, migrate to a behavior tree | 10-14h |
| F | Packaging: Hugging Face Space, one-click install, CI, contribution guide | 10-14h |
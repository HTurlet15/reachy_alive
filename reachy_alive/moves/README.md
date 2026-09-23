# Making a move

A **move** is one gesture the robot plays — a yawn, a stretch, a hiccup.
Everything around it is already handled: when it gets triggered, how its
sounds reach the robot, how it hands the robot back. All you write is the
gesture itself.

## The contract

Most gestures are a sequence of phases, each timed by its own sound.
`PhasedMove` handles all of that; you declare the phases and write the
poses:

```python
from reachy_alive.moves.base import Move, PhasedMove


class YourMove(PhasedMove):
    """Plays a hand-made move."""

    SOUNDS_DIR = Move.SOUNDS_DIR / "your_move"

    PHASE_SOUNDS = {"rise": "rising.wav", "fall": "falling.wav"}

    def _pose_at(self, phase, p, step):
        ...
```

You never call `_pose_at()` yourself. The robot calls `play()`, which:

1. uploads your move's sounds to the robot, while it's still at rest
2. runs the gesture, firing each sound as its phase begins
3. returns the robot to neutral

So you don't have to clean up after yourself, and the next behavior always
starts from a known pose.

If your gesture isn't a sequence of phases, subclass `Move` directly and
write `_perform()` and `sound_paths()` yourself.

## Step 1 — Plan the gesture

Before touching anything, write down the phases. A gesture is a sequence
of distinct moments, each with its own motion and usually its own sound.

As an example, `yawning.py` has four phases:

| Phase | Motion | Sound |
|---|---|---|
| rise | head tilts up, antennas lower | inhale |
| hold | stays there | — |
| exhale | eases back down | the yawn itself |
| shake | head shakes side to side | waking up |

Knowing this list is most of the work. The rest is filling it in.

## Step 2 — Choose how to build the move

Three ways. Pick based on the gesture, not on what you already know.

- **Write it in code** — best when the motion is simple to describe: the
  head rises, holds, comes back. You control it exactly, and you can work
  without the robot in front of you. See `stretching.py` and `yawning.py`.

- **Record it by hand** — best when the motion is organic and awkward to
describe in numbers. Install the **Marionette** app from Reachy Mini
Control, move the head by hand, and it captures everything — sound
included, already in sync.

- **Both** — record the head, code the antennas. This is the answer when
you run out of hands: the head needs your fingers, and the antennas need
to snap faster than you can manage at the same time. Pollen used an HTC
Vive tracker plus a controller for exactly this reason; mixing is the
closest you get without that hardware.

## Step 3 — Make the sound first

Once you've chosen how to build your move, start here, not with the
motion. Timing a gesture to a finished sound is far easier than the other
way round: a sound has a fixed length you can't stretch, while a gesture
bends to fit.

How you package it depends on your choice: **one file per phase** if you
write the move in code, **a single composed file** if you record it in
Marionette. See [`../assets/sounds/README.md`](../assets/sounds/README.md)
— it takes about ten minutes in the browser.

## Step 4 — Create the motion

### If you wrote it in code

You write two things: the phases, and one pose per phase.

**1. The phases**

Each phase lasts exactly as long as its sound, so declaring the sounds
also declares the timing:

```python
PHASE_SOUNDS = {
    "rise": "inhale.wav",
    "hold": None,
    "exhale": "exhale.wav",
    "shake": "shake.wav",
}
SILENT_PHASE_DURATIONS_S = {"hold": 0.7}
PHASE_PADDING_S = {"rise": 0.5}
```

A phase with no sound (`None`) needs a duration in
`SILENT_PHASE_DURATIONS_S`. To add a beat of silence after a sound, use
`PHASE_PADDING_S` rather than editing the `.wav`.

Nothing else to do about sounds: `PhasedMove` lists them for upload and
plays each one as its phase begins.

**2. One pose per phase**

On every tick, `PhasedMove` works out which phase is running and how far
through it, then calls `_pose_at`. Dispatch to one method per phase:

```python
def _pose_at(self, phase, p, step):
    if phase == "rise":
        return self._rise_pose(p)
    ...
```

Each method receives `p`, going from 0 to 1 across its phase, and returns
the head pose, both antenna angles and the body yaw:

```python
def _rise_pose(self, p: float) -> tuple[np.ndarray, list[float], float]:
    pitch = interpolate(0.0, self.RISE_PITCH_DEG, p)
    antenna = interpolate(self.ANTENNA_AT_NEUTRAL_RAD, self.ANTENNA_LOWERED_RAD, p)
    head = create_head_pose(pitch=pitch, degrees=True)
    return head, [antenna, -antenna], NEUTRAL_BODY_YAW_RAD
```

`interpolate(start, end, p)` gives the value `p` of the way from `start`
to `end`. Make each phase start where the previous one ended, or the robot
will jump between them.

The antennas are returned as a pair, so they don't have to move together —
`[antenna, -antenna]` mirrors them, but a gesture is free to drive each
one separately.

The body yaw is the last value. Return `NEUTRAL_BODY_YAW_RAD` unless your
gesture turns the body.

`yawning.py` is the reference for all of this — copy its shape.

The `step` argument is a tick counter, for motion that alternates rather
than interpolates. `yawning.py` uses it to shake, `stretching.py` to
tremble.

---

### If you recorded it in Marionette

There's nothing to write. Marionette uploads each recording to a Hugging
Face dataset under your account. `hiccup-full` was made this way — here's
how it's wired into the idle pool in `main.py`:

```python
reachy_alive_recordings = RecordedMoves("HTurlet15/reachy-alive")

marionette_moves = self._library_moves(reachy_alive_recordings, [
    "hiccup-full",
])
```

Before wiring yours in, check it loads:

```bash
python -c "
from reachy_mini.motion.recorded_move import RecordedMoves
print(RecordedMoves('your-username/your-dataset').list_moves())
"
```

Three things trip people up:

- **The dataset name on the Hub can differ from what Marionette shows.**
  Marionette displays `reachy_alive`; the Hub identifier is
  `reachy-alive`. Check `https://huggingface.co/<your-username>` if a name
  doesn't resolve.
- **The move name is exactly what Marionette saved** — `hiccup-full`, with
  a hyphen, not `hiccup_full`.
- **The dataset must be public**, or the move plays on your machine and
  nowhere else.

---

### If you mixed both

A recorded move exposes `evaluate(t)`, `duration` and `sound_path` — what
`play_move` uses internally. A mixed move subclasses `Move` directly,
plays the recording frame by frame in `_perform()`, and replaces what it
wants — typically the antennas — keeping both halves aligned on the
recording's own timing.

> No example ships yet. If you build one, add it here.

## Step 5 — Try it

For a move written in code, add your class to `_CODED_MOVES` in
`../scripts/try_move.py`. Then:

```bash
pytest                            # checks the logic, no robot needed
try-move your-move                # a move written in code
try-move recorded hiccup-full     # a move recorded in Marionette
try-move pollen boredom1          # one of Pollen's emotions
```

`try-move` eases the robot into neutral before your move and puts it back
to sleep after, so every run starts from the same state.

Expect several rounds of adjusting numbers and watching. That's normal —
the values in `stretching.py` took a lot of passes.

---

## Things that will bite you

**Antennas jitter when perfectly vertical.** Neutral isn't `[0.0, 0.0]`,
it's `NEUTRAL_ANTENNAS_RAD` (~10° off). Start and end your antenna motion
there.

**Your gesture starts from neutral — keep it that way.** `set_target`
doesn't interpolate. Streaming it from a pose far away — the sleep pose
after a fresh boot, say — asks for a huge instant jump and can take the
robot's daemon down. `play()` and `try-move` make sure you start from
neutral; don't bypass them.

**Never send the head below z = -170 mm.** Below that, the robot's
inverse kinematics solver wedges permanently — it keeps accepting
commands and playing sounds while no longer moving, until the daemon is
restarted. The recorded moves `waiting`, `mini-deep-sleep` and
`toc-toc-toc` do this; don't use them
([pollen-robotics/reachy_mini#1417](https://github.com/pollen-robotics/reachy_mini/issues/1417)).

**Use `time.monotonic()`, never `time.time()`.** Wall-clock time can jump
backwards on a clock sync, mid-gesture.

**If you subclass `Move` directly**, play sounds with `self.play_sound()`,
never `reachy_mini.media.play_sound()`. Both work, but only the first uses
the copy already uploaded to the robot; calling the SDK directly
re-uploads the file mid-gesture, and the motion stutters at every sound.
# Making a move

A **move** is one gesture the robot plays — a yawn, a stretch, a sneeze.
Everything around it is already handled: when it gets triggered, how it
ends, how it hands the robot back. All you write is the gesture itself.

## The contract

One file, one class, one method:

```python
from reachy_mini import ReachyMini
from reachy_alive.moves.base import Move


class YourMove(Move):
    """Plays a hand-made move."""

    def _perform(self, reachy_mini: ReachyMini) -> None:
        ...
```

That's it. You never call `_perform()` yourself — the robot calls
`play()`, which runs your gesture and then returns to neutral. You don't
have to clean up after yourself.

---

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

Once you chose how you will create your move, start here, not with the motion. Timing a gesture to a finished sound is far easier than the other way round: a sound has a fixed length you can't
stretch, while a gesture bends to fit.

See [`../assets/sounds/README.md`](../assets/sounds/README.md) — it takes
about ten minutes in the browser.

## Step 4 — Create the motion

### If you wrote it in code

Declare the phases and their sounds, then let `__init__` read the
durations from the files:

```python
PHASE_SOUNDS = {
    "rise": "inhale.wav",
    "hold": None,
    "exhale": "exhale.wav",
    "shake": "shake.wav",
}
HOLD_DURATION_S = 0.7
```

A phase with `None` needs an explicit duration. A phase that needs a beat
of silence after its sound gets an entry in `PHASE_PADDING_S` — a rhythm
setting, tunable without re-exporting anything.

Then compute a pose on every tick and send it with `set_target`, inside
**one continuous loop**. One loop, not a chain of `goto_target` calls —
each of those decelerates to a full stop, and a sequence of them reads as
a stutter rather than a gesture.

Sounds fire when the phase changes:

```python
if phase != previous_phase:
    self._play_phase_sound(reachy_mini, phase)
    previous_phase = phase
```

`yawning.py` is the reference for all of this — copy its shape.

---

### If you recorded it in Marionette

There's nothing to write. Publish the recording as a Hugging Face dataset
and use it directly:

```python
from reachy_mini.motion.recorded_move import RecordedMoves
from reachy_alive.moves.base import LibraryMove

my_moves = RecordedMoves("your-username/your-dataset")
itching = LibraryMove("itching", my_moves)
```

See `itching` in `main.py` for a working example.

---

### If you mixed both

Write a `Move` subclass that plays the recorded head motion and drives
the antennas from code. Take the gesture's duration from the sound file
so both halves stay aligned:

```python
self.duration_s = sf.info(str(self.SOUND_PATH)).duration
```

See `sneezing.py`.

## Step 5 — Try it

Add your class to `_MOVES` in `../scripts/try_move.py`, then:

```bash
pytest                    # checks the logic, no robot needed
try-move your-move        # plays it on the real robot
```

Expect several rounds of adjusting numbers and watching. That's normal —
the values in `stretching.py` took a lot of passes.

---

## Three things that will bite you

**Antennas jitter when perfectly vertical.** Neutral isn't `[0.0, 0.0]`,
it's `NEUTRAL_ANTENNAS_RAD` (~10° off). Use that constant.

**Never send the head below z = -170 mm.** Below that, the robot's
inverse kinematics solver wedges permanently — it keeps accepting
commands and playing sounds while no longer moving, until the daemon is
restarted. The recorded moves `waiting`, `mini-deep-sleep` and
`toc-toc-toc` do this; don't use them.

**Use `time.monotonic()`, never `time.time()`.** Wall-clock time can jump
backwards on a clock sync, mid-gesture.
# Making a move

A **move** is one gesture the robot plays — a yawn, a stretch, a sneeze.
Everything around it is already handled: when it gets triggered, how it
ends, how it gives the robot back. All you write is the gesture itself.

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
TO DO : Step 0 : Think about what you want to do - number of phases, sound, movement you want to do. Exemple avec yawning 4 phases : montée inhale + pause + Relache longue avec baillement en redescente + secouer pour se réveiller

## Step 1 — Make the sound first

Start here, not with the motion. Timing a gesture to a finished sound is
far easier than the other way round: a sound has a fixed length you can't
stretch, while a gesture bends to fit.

See [`../assets/sounds/README.md`](../assets/sounds/README.md) — it takes
about ten minutes in the browser.

## Step 2 — Choose how to build the motion

Three ways. Pick based on the gesture, not on what you already know.

**Write it in code** — best when the motion is simple to describe: the
head rises, holds, comes back. You control it exactly, and you can work
without the robot in front of you. See `stretching.py` and `yawning.py`.

**Record it by hand** — best when the motion is organic and awkward to
describe in numbers. Install the **Marionette** app from Reachy Mini
Control, move the head by hand, and it captures everything — sound
included, already in sync.

**Both** — record the head, code the antennas. This is the answer when
you run out of hands: the head needs your fingers, and the antennas need
to snap faster than you can manage at the same time. Pollen used an HTC
Vive tracker plus a controller for exactly this reason; mixing is the
closest you get without that hardware.

## Step 3 — Write it

### If you recorded it in Marionette

Nothing to write at all. Publish the recording as a Hugging Face dataset
and use it directly:

```python
from reachy_mini.motion.recorded_move import RecordedMoves
from reachy_alive.moves.base import LibraryMove

my_moves = RecordedMoves("your-username/your-dataset")
sneezing = LibraryMove("sneezing", my_moves)
```

### If you're writing the motion

Compute a pose on every tick and send it with `set_target`, inside **one
continuous loop**:

```python
start = time.monotonic()
while time.monotonic() - start < self.DURATION_S:
    progress = (time.monotonic() - start) / self.DURATION_S
    pitch, yaw = self._pose_at(progress)
    pose = create_head_pose(pitch=pitch, yaw=yaw, degrees=True)
    reachy_mini.set_target(head=pose, antennas=[...])
    time.sleep(self.step_s)
```

One loop, not a chain of `goto_target` calls — each of those decelerates
to a full stop, and a sequence of them reads as a stutter rather than a
gesture.

For a gesture with distinct phases (rise, hold, return), express each
phase as a fraction of the total and dispatch on `progress`.
`yawning.py` does this with four phases; copy its shape.

### Playing your sound at the right moment

Fire it when `progress` crosses a threshold, with a flag so it only plays
once:

```python
if progress >= self.RISE_END and not self._sound_played:
    reachy_mini.media.play_sound(str(self.SNEEZE_SOUND_PATH))
    self._sound_played = True
```

Reset that flag at the top of `_perform()` — the same object is reused
every time the move is triggered.

There's a small delay between the call and the audible sound, so you'll
probably need to fire slightly before the visual beat. Tune by ear on the
real robot.

## Step 4 — Try it

Add your class to `_MOVES` in `../scripts/try_move.py`, then:

```bash
pytest                    # checks the logic, no robot needed
try-move sneezing         # plays it on the real robot
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
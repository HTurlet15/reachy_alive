# Mixing a recording and code

A mixed move is a regular `PhasedMove` whose head is read from a
Marionette recording instead of computed. `sneezing.py` is the reference.

Read [`CODED_MOVES.md`](CODED_MOVES.md) first — phases, poses and `p` work exactly
the same here. For the steps before and after this one, see
[`README.md`](README.md).

## 1. Package the sounds — both ways

You need one `.wav` per phase, as for a move written in code, **and** a
`compose.py` that joins those same parts into a single file, as for a
move recorded in Marionette — see
[Several parts in one file](../assets/sounds/README.md#several-parts-in-one-file).

## 2. Record the head against the composed file

Record the head in Marionette against the composed file (see
[`MARIONETTE_MOVES.md`](MARIONETTE_MOVES.md)). Since that file is built from the
phase sounds, the recording's timeline and the phases are the same: a
phase boundary is a moment in the recording, for free.

## 3. Declare the phases exactly as `compose.py` does

Same sounds, same order, same silences in `PHASE_PADDING_S`. Nothing
checks this: if the two diverge, the head drifts away from the sounds
without any error. Leave a comment in both files pointing to the other.

## 4. Read the head, code the rest

Load the recording in the constructor, and read it in `_pose_at`:

```python
def __init__(self, library: RecordedMoves, tick_hz: float = 50.0) -> None:
    super().__init__(tick_hz)
    self._recording = library.get("sneezing")

def _pose_at(self, phase, p, step, elapsed_s):
    t = min(elapsed_s, self._recording.duration)
    head, _, body_yaw = self._recording.evaluate(t)
    antenna = ...
    return head, [antenna, -antenna], body_yaw
```

Read the recording with `elapsed_s`, not `p`: the recording is one
continuous timeline, while `p` restarts at every phase. The `min` guards
against float rounding at the very end.

The recording's own sound is never played — `PhasedMove` plays the phase
sounds, so there's no double audio.

Code what a hand can't do: a fast shake, a drop in a few ticks, a
variation between plays. `sneezing.py` draws its drop angle in
`_perform()`, then hands over to `PhasedMove`.

## Register it

A mixed move needs the recordings library, so pass it in `main.py`:

```python
mixed_moves = [Sneezing(reachy_alive_recordings)]
```

And add the class to `_MIXED_MOVES` in `../scripts/try_move.py`.
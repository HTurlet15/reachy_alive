# Writing a move in code

You write the phases and one pose per phase; `PhasedMove` does the rest.
`yawning.py` is the reference — copy its shape. For the steps before and
after this one, see [`README.md`](README.md).

## Package the sounds

One `.wav` per phase, in `assets/sounds/<your_move>/`. Silences between
phases don't go in the files — they go in `PHASE_PADDING_S`, below.

## The skeleton

```python
from reachy_alive.moves.base import Move, PhasedMove


class YourMove(PhasedMove):
    """Plays a hand-made move."""

    SOUNDS_DIR = Move.SOUNDS_DIR / "your_move"

    PHASE_SOUNDS = {"rise": "rising.wav", "fall": "falling.wav"}

    def _pose_at(self, phase, p, elapsed_s):
        ...
```

You never call `_pose_at()` yourself: `PhasedMove` calls it on every tick,
and plays each phase's sound as the phase begins.

## 1. The phases

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

## 2. One pose per phase

On every tick, `PhasedMove` works out which phase is running and how far
through it, then calls `_pose_at`. Dispatch to one method per phase:

```python
def _pose_at(self, phase, p, elapsed_s):
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
`[antenna, -antenna]` mirrors them, but a move is free to drive each
one separately.

The body yaw is the last value. Return `NEUTRAL_BODY_YAW_RAD` unless your
move turns the body.

The last argument, `elapsed_s`, is the time since the move started.
Unlike `p`, it doesn't reset between phases. Most phases ignore it; it
serves two cases:

- motion that alternates rather than interpolates, like a shake or a
  tremble. Give it to `alternating_sign`, which returns +1 or -1 and
  switches every half period, in seconds:

  ```python
  sign = alternating_sign(elapsed_s, self.SHAKE_HALF_PERIOD_S)
  ```

  `yawning.py` uses it to shake, `stretching.py` to tremble. Keep
  alternations at 0.02 s per side or slower: faster ones don't reach the
  robot.
- reading a recording, which runs on a single timeline —
  [`MIXED_MOVES.md`](MIXED_MOVES.md) explains it.

## 3. Vary between plays

Optional. A move that plays exactly the same every time looks
mechanical. To vary something from one play to the next — an angle, an
amplitude — draw it in `_on_start()`, store it on `self`, and read it in
`_pose_at`:

```python
def __init__(self, tick_hz: float = 50.0) -> None:
    super().__init__(tick_hz)
    self._drop_angle_rad = self.DROP_ANGLE_RAD

def _on_start(self) -> None:
    self._drop_angle_rad = self.DROP_ANGLE_RAD + random.uniform(-0.1, 0.1)
```

`PhasedMove` calls `_on_start()` once at the start of every play, before
the first pose. Draw there, not elsewhere:

- not in `_pose_at`, which runs on every tick: the value would change
  50 times a second;
- not in `__init__`, which runs once for the whole session: every play
  would get the same value.

Keep a default in `__init__`, as above: the tests read poses without
playing the move, so `_on_start()` never runs for them.

`sneezing.py` uses this to vary how far its antennas drop.

## Register it

Add it to `coded_moves` in `main.py`, to `_CODED_MOVES` in
`../scripts/try_move.py`, and to `MOVES` in
`tests/moves/test_pose_contract.py` — that test checks every pose follows
the contract and never sends the head below the reachable workspace.
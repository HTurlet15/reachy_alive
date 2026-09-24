# Making a move

A **move** is one gesture the robot plays — a yawn, a stretch, a hiccup.
Everything around it is already handled: when it gets triggered, how its
sounds reach the robot, how it hands the robot back. All you make is the
gesture itself.

This page is the path every move follows. Step 2 sends you to the page
for the way you build yours.

## What the robot does with your move

The robot calls the move's `play()`, which:

1. uploads its sounds to the robot, while it's still at rest
2. runs the gesture
3. returns the robot to neutral

So you never clean up after yourself, and the next behavior always starts
from a known pose.

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

- **Write it in code** → [`coded.md`](coded.md). Best when the motion is
  simple to describe: the head rises, holds, comes back. You control it
  exactly, and you can work without the robot in front of you.
- **Record it by hand** → [`marionette.md`](marionette.md). Best when the
  motion is organic and awkward to describe in numbers. You move the head
  by hand in the Marionette app, and it captures everything.
- **Both** → [`mixed.md`](mixed.md). Record the head, code the antennas.
  The answer when you run out of hands: the head needs your fingers, and
  the antennas need to move faster than you can manage at the same time.

Each way has a move you can copy:

| Way | Example | Where |
|---|---|---|
| Code | yawning (the reference), stretching | `yawning.py`, `stretching.py` |
| Marionette | hiccup | `hiccup-full` in the `HTurlet15/reachy-alive` dataset |
| Mixed | sneezing | `sneezing.py` |

## Step 3 — Make the sound first

Start here, not with the motion. Timing a gesture to a finished sound is
far easier than the other way round: a sound has a fixed length you can't
stretch, while a gesture bends to fit.

[`../assets/sounds/README.md`](../assets/sounds/README.md) shows how to
make one — about ten minutes in the browser. Your path's page says how to
package it.

## Step 4 — Create the motion

Follow your path's page: [`coded.md`](coded.md),
[`marionette.md`](marionette.md) or [`mixed.md`](mixed.md).

## Step 5 — Try it

Your path's page says how to register the move in `main.py` and
`../scripts/try_move.py`. Then:

```bash
pytest                            # checks the logic, no robot needed
try-move your-move                # a move written in code or mixed
try-move recorded hiccup-full     # a move recorded in Marionette
try-move pollen boredom1          # one of Pollen's emotions
```

`try-move` eases the robot into neutral before your move and puts it back
to sleep after, so every run starts from the same state.

Expect several rounds of adjusting and watching. That's normal — the
values in `stretching.py` took a lot of passes.

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
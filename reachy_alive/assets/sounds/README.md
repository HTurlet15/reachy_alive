# Sounds

Short audio clips played during moves and reactions. Pollen's own robot
sounds were made with a slide whistle, so anything added here should stay
in that family: a **round, sustained tone that glides** — not a
video-game blip.

This page shows how to make a sound. How to package it for your move
depends on how you build the move — see
[`../../moves/README.md`](../../moves/README.md).

## Layout

Sounds are grouped by the move that uses them:

```
assets/sounds/
├── base.jsfxr.json            ← the shared starting point
├── yawning/                   ← written in code: one sound per phase
│   ├── inhale.wav
│   ├── inhale.jsfxr.json
│   └── ...
├── hiccup/                    ← recorded in Marionette: one composed sound
│   ├── hiccup.wav
│   ├── hiccup.jsfxr.json
│   ├── complaining.wav
│   ├── complaining.jsfxr.json
│   ├── compose.py             ← joins the parts
│   └── hiccup_full.wav        ← the result, played during the recording
└── sneezing/                  ← mixed: both
    ├── inhale1.wav            ← one sound per phase...
    ├── ...
    ├── compose.py
    └── sneezing.wav           ← ...and the composed file, for the recording
```

Create a folder named after your move, and keep each `.wav` next to the
preset that produced it. The preset is what lets the next person pick up
where you left off.

## Create a sound

Build it in [jsfxr](https://sfxr.me) — in the browser, nothing to install.

Don't start from scratch: load [`base.jsfxr.json`](base.jsfxr.json) and
change **Start frequency** and **Slide** first — they carry most of the
character. Same voice, different moods: that's what keeps every sound in
the project sounding like the same robot.

Two ways to load it:

- **Open Save**, then pick [`base.jsfxr.json`](base.jsfxr.json) from disk.
- **Deserialize**: click it to open the text box, paste in the file's
  JSON content, then click **Deserialize** again to apply it.

  ![jsfxr Deserialize panel](../../../docs/jsfxr-deserialize.png)

Once loaded, the generator panel reflects the preset's settings — this is
what `base.jsfxr.json` looks like:

![jsfxr generator panel with the base preset loaded](../../../docs/jsfxr-settings.png)

From there, adjust until it fits your move, but stay close to the base
preset's tone so the robot doesn't sound like a different creature from
one move to the next.

Export **both** files into your move's folder: the `.wav`, and — via
*Serialize* or *Save* — the `.json` preset.

> jsfxr can't mix noise into a sine wave, so you won't get the breathiness
> of a real whistle. Close is good enough.

## Several parts in one file

Needed for moves recorded in Marionette, and for mixed moves.

Marionette plays a single sound while you move the robot by hand — that
sound is your metronome during the take. So a gesture with several beats
needs its parts, and the silences between them, joined into one file.

Build each part separately in jsfxr, then keep a `compose.py` next to
them that joins them. [`hiccup/compose.py`](hiccup/compose.py) is the
reference:

```python
concatenate(
    [
        (str(HERE / "hiccup.wav"), 0.6),
        (str(HERE / "hiccup.wav"), 0.6),
        (str(HERE / "hiccup.wav"), 0.9),
        (str(HERE / "complaining.wav"), 0.7),
        (str(HERE / "hiccup.wav"), 0.0),
    ],
    str(HERE / "hiccup_full.wav"),
)
```

Each number is the silence *after* that part, in seconds. Those silences
are the gesture's rhythm: compose the file, listen to it a few times, and
rehearse the motion against it before recording.

All parts must share the same sample rate (jsfxr exports at 44k, 22k, 11k
or 8k). Mixing rates plays the result at the wrong speed.
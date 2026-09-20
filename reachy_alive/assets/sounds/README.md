# Sounds

Short audio clips played during moves and reactions. Pollen's own robot
sounds were made with a slide whistle, so anything added here should stay
in that family: a **round, sustained tone that glides** — not a
video-game blip.

## Layout

Sounds are grouped by the move that uses them:

```
assets/sounds/
├── base.jsfxr.json ← the shared starting point
└── yawning/
    ├── inhale.wav
    ├── inhale.jsfxr.json
    ├── exhale.wav
    ├── exhale.jsfxr.json
    ├── shake.wav
    └── shake.jsfxr.json
```

Create a folder for your move, and keep each `.wav` next to the preset
that produced it. The preset is what lets the next person pick up where
you left off.

## Create a sound

Build it in [jsfxr](https://sfxr.me), in the browser, nothing to install.
You don't have to start from scratch: load [`base.jsfxr.json`](base.jsfxr.json)
and change the settings, like **Start frequency** and **Slide**. Same
voice, different moods. That's what keeps every sound in the project
sounding like the same robot.

Two ways to load it in jsfxr:

- **Open Save**, then pick [`base.jsfxr.json`](base.jsfxr.json) from disk.
- **Deserialize**: click it to open the text box, paste in the file's
  JSON content, then click **Deserialize** again to apply it.

  ![jsfxr Deserialize panel](../../../docs/jsfxr-deserialize.png)

Once loaded, the generator panel reflects the preset's settings — this
is what `base.jsfxr.json` looks like:

![jsfxr generator panel with the base preset loaded](../../../docs/jsfxr-settings.png)

Play with the different values to find the perfect sound for your move. 
Try to keep it in the same tone of the base.jxsfr.json, so the 
robot doesn't sound too different between moves.

Export **both** files: the `.wav` and — via *Serialize* or *Save* — the
`.json` preset into your move folder. The preset is what lets the next person
pick up where you left off.

> jsfxr can't mix noise into a sine wave, so you won't get the
> breathiness of a real whistle. Close is good enough.

## Play a sound (for moves written with code)

```python
reachy_mini.media.play_sound(str(MY_SOUND_PATH))
```

Non-blocking, so a gesture keeps running while the sound plays. See
[`../../moves/README.md`](../../moves/README.md) for how to fire it at
the right moment in a gesture.

## Concatenating several parts (for moves created with Marionette)

If you chose to create your move with the Marionette app, you will need one 
`.wav` of all your different sounds you just created since Marionette doesn't 
support having multiples phases sounds.


For example, a sneeze is a sniff, a pause, then the sneeze itself. Build each part
separately in jsfxr, then join them:

```python
from reachy_alive.scripts.compose_sound import concatenate

concatenate(
    [("sniff.wav", 0.3), ("sneeze.wav", 0.15), ("sigh.wav", 0.0)],
    "sneezing.wav",
)
```

Each number is the silence *after* that part, in seconds. Those silences
are what give the sound its rhythm — expect to try a few values.

In this example, you will get a final `sneezing.wav` of `sniff.wav` + 0.3s of silence,
then `sneeze.wav` + 0.15s of silence and finally `sigh.wav`.

All parts must share the same sample rate (jsfxr exports at 44k, 22k, 11k
or 8k). Mixing rates plays the result at the wrong speed.
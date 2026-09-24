# Recording a move in Marionette

There's no code to write: you move the robot by hand, and the recording
is played as-is. For the steps before and after this one, see
[`README.md`](README.md).

## Package the sound

Marionette plays a single sound during the take, so join your parts and
their silences into one file with a `compose.py` — see
[Several parts in one file](../assets/sounds/README.md#several-parts-in-one-file)
in the sounds README.

## Record

Install the **Marionette** app from Reachy Mini Control, load your
composed sound, and move the head by hand along with it. Marionette
captures the motion and the sound together, already in sync, and uploads
the recording to a Hugging Face dataset under your account.

Before wiring it in, check it loads:

```bash
python -c "
from reachy_mini.motion.recorded_move import RecordedMoves
print(RecordedMoves('your-username/your-dataset').list_moves())
"
```

Four things trip people up:

- **The dataset name on the Hub can differ from what Marionette shows.**
  Marionette displays `reachy_alive`; the Hub identifier is
  `reachy-alive`. Check `https://huggingface.co/<your-username>` if a name
  doesn't resolve.
- **The move name is exactly what Marionette saved** — `hiccup-full`, with
  a hyphen, not `hiccup_full`.
- **The dataset must be public**, or the move plays on your machine and
  nowhere else.
- **A move recorded after your first download stays invisible**
  (`Move X not found`): the dataset is cached locally. Clear it with
  `rm -rf ~/.cache/huggingface/hub/datasets--<user>--<dataset>`.

## Register it

`hiccup-full` was made this way — here's how it's wired into the idle
pool in `main.py`:

```python
reachy_alive_recordings = RecordedMoves("HTurlet15/reachy-alive")

marionette_moves = self._library_moves(reachy_alive_recordings, [
    "hiccup-full",
])
```

Nothing to add to `try_move.py`: play it with
`try-move recorded your-move-name`.

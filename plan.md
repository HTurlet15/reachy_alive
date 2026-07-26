# Reachy Alive — Master Plan

## 0. How to read this document

This plan is the single reference for the project. For every technical decision it answers three questions:
- **What** — what the component does
- **Why** — why this choice over a credible alternative
- **How** — how it talks to the rest of the system

Goal: reach the coding phase with zero architectural ambiguity. Fine-grained decisions (exact function names, etc.) stay open for the coding phase itself, but every structuring decision is made here.

This version supersedes the French draft and has been **cross-checked against the official `pollen-robotics/reachy_mini` `AGENTS.md`** (the SDK's own guide for AI coding agents). Section 1 bis below lists every point where the official guide corrected or refined an assumption from the first draft — read it even if you already know the rest of the plan.

---

## 1. Project philosophy

### 1.1 The problem we're solving

A classic "slave" robot (like most Reachy demos) waits for a command, executes it, then freezes. It's a state machine, not a being. The core technical problem: **generative AI is slow (1–3 seconds per call), but a living body must move continuously and smoothly even when it isn't thinking about anything in particular.**

If everything sits in one loop (perceive → think via LLM → move), the robot freezes for 1–3 seconds on every interaction. That isn't "alive" — it's a chatbot with arms.

### 1.2 The solution: strict separation of frequencies

The solution comes from computational neuroscience: the human body doesn't consciously decide to breathe, blink, or pull a hand off a hot plate. These behaviors are handled by fast circuits that are independent of the (slow) conscious cortex. We replicate that:

| Layer | Frequency | Ever blocks? |
|---|---|---|
| Brainstem (motor) | Internal decision loop ~50 Hz; commands sent to the robot at ≥10 Hz (SDK requirement, see 1 bis) | Never — the absolute rule of the project |
| Sensory cortex (perception) | 5–30 Hz depending on sensor | No, runs in parallel |
| Hippocampus / Amygdala | Event-driven | No, lightweight SQLite queries |
| Prefrontal cortex (LLM) | 0.2–1 Hz (1–3 s/call) | Yes, but **isolated in its own thread/process** |

All the architectural complexity of this project follows from this one constraint: **isolate what is slow from what must be fast, so the slow part never blocks the fast part.**

---

## 1 bis. Reconciliation with the official `reachy_mini` AGENTS.md

Before finalizing anything, I read the SDK's own agent guide (`pollen-robotics/reachy_mini/AGENTS.md`). It confirms most of the original plan but corrects several concrete details. Here is what changed and why it matters:

### a) Correct SDK import and object

The real SDK is the `reachy_mini` Python package (not a generic `reachy-sdk` name):

```python
from reachy_mini import ReachyMini

with ReachyMini() as mini:
    ...
```

Impact: `brainstem/engine.py` will use this exact import and context-manager pattern, not a placeholder.

### b) Two motion methods, not one generic "send command"

| Method | Use when |
|---|---|
| `goto_target()` | **Default.** Smooth, interpolated motion for gestures lasting at least 0.5 s (e.g. an emotion animation). |
| `set_target()` | Real-time control loops (e.g. face tracking), **recommended at 10 Hz or more.** |

Impact on our design: the plan's "strictly 50 Hz" rule was a self-imposed choice for smoothness, not an SDK requirement — the SDK only asks for **10 Hz minimum** on `set_target()`. We keep our internal Brainstem decision loop at 50 Hz (finer blending, no downside), but this means we have comfortable headroom relative to the SDK's own minimum, and it clarifies which of our behaviors should call `goto_target()` (discrete emotion gestures) versus `set_target()` (continuous tracking/breathing).

### c) A ready-made emotions library — don't reinvent idle/reaction animations from scratch

Pollen ships a pre-recorded motion library:

```python
from reachy_mini.motion.recorded_move import RecordedMoves

moves = RecordedMoves("pollen-robotics/reachy-mini-emotions-library")
mini.play_move(moves.get("happy"), initial_goto_duration=1.0)
```

This is a significant simplification for the **Amygdala**: instead of hand-coding a "surprise" motion in `reflexes.py`, `reactions.py` can call `mini.play_move(moves.get("surprise"))` directly. Our own procedural code (sine-wave breathing, idle micro-movements) is still needed for the *continuous* idle behavior — the library covers discrete, expressive *reactions*. Decision: use the library for reactions/emotions, keep procedural code only for continuous idle/tracking motion.

### d) Hardware model is more specific than "motors"

- **Head**: 6 DOF (x, y, z, roll, pitch, yaw) via a Stewart platform — motor names `stewart_1` to `stewart_6`.
- **Body**: rotation only, around the vertical axis — motor name `body_rotation`.
- **Antennas**: 2 motors, also usable as physical buttons — `right_antenna`, `left_antenna`.

Impact: `reflexes.py` needs to reason in terms of these four addressable groups, not a generic joint array. The antennas being usable as *input buttons* is a free interaction channel we hadn't planned for — worth considering for a later phase (e.g. a physical "get my attention" gesture).

### e) Hard safety limits

| Joint | Range |
|---|---|
| Head pitch/roll | ±40° |
| Head yaw | ±180° |
| Body yaw | ±160° |
| Yaw delta (head − body) | max 65° |

The SDK clamps these automatically, but `reflexes.py` should still respect them by design (not rely solely on clamping) — an idle sine wave with too large an amplitude shouldn't silently get truncated every cycle, it should be authored within range from the start.

### f) Hardware variant: Lite vs Wireless — **confirmed: Wireless**

- **Lite**: USB to a laptop, full compute available on the host machine.
- **Wireless**: onboard CM4, WiFi. Two sub-modes per the official platform-compatibility table: *Wireless (local)* runs everything on the CM4 itself (memory/CPU constrained), while *Wireless (streamed)* keeps full laptop compute and reaches the robot's camera/mic over the network, at the cost of some tracking-quality loss from network latency.

Hugo's hardware is **Wireless**. Given Reachy Alive needs YOLOv8/MediaPipe, Whisper, SQLite, and an LLM running concurrently, running all of that *on the CM4 itself* is not realistic (too little compute). **Decision: Wireless in streamed mode** — all cognitive modules (Brainstem, Sensory Cortex, Hippocampus, Amygdala, Prefrontal Cortex) run on the x86 laptop, exactly as originally planned; only the robot's camera/mic/motors are reached over WiFi instead of USB. This matches the original execution-environment brief ("local x86 machine communicating with the robot over the network") almost exactly — WiFi replaces USB as the transport, nothing else changes architecturally.

**One new consequence to track:** camera frames now travel over WiFi before reaching `vision.py`, adding variable network latency on top of inference time. This mainly affects face-tracking smoothness (the `set_target()` loop), not the 50 Hz Brainstem loop itself, since the Brainstem never waits on perception — it only reads whatever the Shared State last held. Worth measuring actual round-trip latency in step 1 of the roadmap before assuming it's negligible.

### g) Python app vs JS/Web app — an explicit, justified choice

The official guide's default recommendation for *any* new Reachy Mini agent is a **JS/Web app** (zero-install, shareable by URL, runs in the browser over WebRTC), and it explicitly says: *"When unsure, start JS."* Python is reserved for cases needing heavy on-robot compute, rich hardware access, deterministic real-time control loops, or offline/LAN tooling.

Reachy Alive falls squarely into the Python category: continuous local vision/audio inference, a 50 Hz real-time control loop, and a local SQLite memory are exactly the criteria the guide lists as justifying Python over JS. This isn't a default we're ignoring — it's the documented exception case. **Decision: Python app**, scaffolded with the SDK's own tooling (next point).

### h) Never hand-create the app folder — use `reachy-mini-app-assistant` (default template, not `conversation`)

The guide is explicit: *"NEVER create app folders manually — use `reachy-mini-app-assistant`."* The `conversation` template was tried and didn't scaffold cleanly, so **decision: use the plain default template instead:**

```bash
reachy-mini-app-assistant create reachy_alive <path> --publish
```

Practical implication: the default template gives us the minimal, safe app skeleton (`pyproject.toml`, entry point, `static/` if needed) but **no pre-wired LLM/speech plumbing** — so `prefrontal_cortex/ai_client.py` and `speech.py` are built from scratch after all, exactly as originally planned in section 2.5, now finalized with Ollama and gTTS. This actually simplifies section 5: our five cognitive modules are added cleanly inside the default package layout, with nothing pre-existing to reconcile against.

Still worth a look, purely as a reference (not as a scaffold to build from): **`reachy_mini_conversation_app`** on GitHub demonstrates AI integration, control loops, and LLM tool use on this exact SDK, and can be a useful sanity check once `ai_client.py`/`speech.py` are written.

### i) The official guide itself mandates a `plan.md` with open questions

Interestingly, the AGENTS.md tells agents to *always create a `plan.md` before coding, list the technical approach, and add clarifying questions with answer fields directly in the file, then wait for the user's answers.* This plan already follows that spirit; section 9 below formalizes it with explicit answer fields, per the official convention.

### j) Having now read the `reachy_mini_conversation_app` README in full — confirms it's a reference, not a scaffold

Its architecture is genuinely different from ours: it's a **turn-based, LLM-tool-calling** app — a realtime voice model (Hugging Face's speech-to-speech backend) drives the conversation, and the LLM explicitly calls tools like `play_emotion`, `dance`, `move_head`, `sweep_look`, or even `idle_do_nothing` on each turn. There's no always-on 50 Hz reflex loop, no Amygdala-style bypass, no fear/startle detection — idle behavior there means the LLM *choosing* to do nothing on a given turn, not an autonomous timer-based scheduler like ours (2.1). This confirms our earlier read: it's the right reference for good patterns, not a base to build on, since our core goal (continuous autonomous "aliveness" that never waits on the LLM) is exactly what its architecture doesn't attempt.

That said, three concrete patterns are worth borrowing as confirmed, tested conventions:
- **Sound bundled with moves** — its `play_emotion` tool plays a recorded clip's *sound* alongside the motion by default, the same mechanism our phased TTS decision (2.5) leans on for phase 1.
- **`sweep_look`** — confirms the procedural look-around pattern already adopted in 2.1.
- Both open Hugging Face datasets (`reachy-mini-emotions-library`, `reachy-mini-dances-library`) are exactly what we already planned to use — good confirmation, not a change.

---

## 2. Cognitive architecture — module by module

### 2.1 Brainstem (`brainstem/`) — the brainstem

**Real role:** the only part of the system with direct, permanent access to the robot via `ReachyMini`. Nobody else talks to the motors.

**What it does every cycle:**
1. Reads the shared state — *read-only, never waits*
2. Computes the current target: either a procedural idle animation (breathing sine wave, idle micro-movements) via `set_target()`, or a discrete emotion gesture from the recorded-moves library via `goto_target()` / `play_move()`, or an interpolation toward a target requested by the Amygdala or Prefrontal Cortex
3. Sends the motor command
4. Does *nothing else*. No network calls, no heavy computation, no waiting for a response.

**Why a sine wave for breathing rather than a recorded clip?**
A sine wave is parametrizable in real time (amplitude = energy level, frequency = emotional state) with no dataset or file to load, and it's trivially interruptible — it can be summed with another motion (e.g. face tracking) with no special-case code, whereas a fixed recording must be played back as-is. Discrete emotional reactions (surprise, happiness), on the other hand, are exactly what the official emotions library already covers (see 1 bis-c) — no need to hand-author those.

**Idle is not just breathing — spontaneous idle gestures (yawn, stretch, look around)**

Breathing is the *continuous* idle layer — it never stops, it's always summed into whatever else is happening. On top of it, we add a *second, discrete* idle layer: every so often, if nothing else is claiming the robot's attention, it plays a one-off gesture (yawn, stretch, glance around) and then resumes breathing. This is what actually reads as "alive" rather than "idling."

Two real sources exist for this content, found by checking Pollen's own libraries and their reference conversation app rather than assuming:
- **`pollen-robotics/reachy-mini-dances-library`** already ships an explicit *subtle/idle* category — moves like `side_to_side_sway` and `pendulum_swing`, literally tagged for "idle", "waiting", "processing" states in Pollen's own mapping. This is the natural first source for idle variety, loaded the same way as the emotions library (`RecordedMoves("pollen-robotics/reachy-mini-dances-library")`).
- **"Look around"** is commonly done *procedurally*, not from a recorded clip — Pollen's own reference conversation app ships a custom tool for exactly this (`sweep_look.py`), built on `goto_target(head=create_head_pose(...))` with randomized yaw/pitch targets within the safety limits (1 bis-e). We'll follow the same pattern rather than inventing our own.
- **Yawn / stretch specifically**: not confirmed by name in either official library from what I could find — this needs a quick empirical check at coding time (`moves.list_moves()` on both libraries, or the `discover()`-style helper some community tools expose) before assuming they exist. If they don't, this becomes the first real candidate for a custom recorded move — worth prioritizing ahead of the rest of the "phase 8" custom-moves backlog (section 7, section 9 Q4) specifically because it's core to the "alive" feeling Hugo wants, not a nice-to-have.

**Who decides when to play an idle gesture, and how does it not fight with a reaction?**
This is a new small responsibility, distinct from both the Amygdala (reacts to perception) and the Prefrontal Cortex (reacts to conversation): a lightweight, time-based scheduler that lives in the Brainstem's own domain, since it needs no perception, no memory, and no LLM — just a timer and a bit of randomness. Concretely:
- A small state (call it `idle_scheduler`, e.g. in a new `brainstem/idle_behaviors.py`) tracks time since the last discrete gesture and time since the last *external* target (from Amygdala or Prefrontal Cortex).
- On a randomized interval (e.g. every 15–40 s), if no external target has been set recently, it picks a gesture from the dance-library idle set or triggers a procedural look-around, plays it once, then falls back to breathing.
- **Priority rule, so idle gestures never fight a reaction:** external targets (Amygdala's surprise, Prefrontal Cortex's expressive speech gestures) always pre-empt and reset the idle timer — the spontaneous idle layer only ever fills the silence, it never overrides a real reaction. This needs one small addition to the Shared State (3.1): a `last_external_command_at` timestamp, so the Brainstem can tell "is anything else currently claiming attention?" without any module needing to ask another directly.

**Why an internal 50 Hz loop when the SDK only asks for 10 Hz?**
50 Hz gives finer blending of procedural motion (smoother breathing, smoother tracking) and comfortable headroom above the SDK's own minimum for `set_target()`. It costs nothing extra locally — the constraint is on this thread never blocking, not on hitting an exact frequency ceiling.

### 2.2 Sensory Cortex (`sensory_cortex/`) — perception

**Real role:** turn a raw video/audio stream into compact semantic text ("I see a cat", "I hear 'hello'"). The Sensory Cortex doesn't *decide* anything, it *describes*.

**Vision — why MediaPipe/YOLOv8 and not a cloud VLM (e.g. GPT-4V)?**
A cloud VLM for continuous detection would cost money per frame and reintroduce the same latency we're trying to isolate. MediaPipe (faces, poses) and YOLOv8 (objects) run locally in a few milliseconds on CPU or a modest GPU. Rich semantic reasoning (cloud, slow) is reserved for the Prefrontal Cortex, which only needs it occasionally, not frame by frame.

**Audio — why local Whisper rather than a cloud STT API?**
Two reasons: latency (Whisper `small`/`base` runs near real-time on a modern CPU with no network round-trip) and continuity — the microphone must listen permanently, which would be costly with a cloud API billed per second.

**Audio also carries a second, separate signal: sudden loud noise.** This is not Whisper's job — transcription is too slow and too speech-specific for a "was that a bang?" check. Instead, `hearing.py` runs a cheap, continuous amplitude/RMS check on the raw audio buffer, independent of the Whisper pipeline, and flags a spike straight to the Shared State for the Amygdala's fear reflex (2.4).

### 2.3 Hippocampus (`hippocampus/`) — episodic memory

**Real role:** keep a record of previously seen objects/faces and compute a **novelty gauge** (0–100) per recognized object.

**Why SQLite and not ChromaDB (vector store) from day one?**
The initial need is structured and simple: `object_id, encounter_count, last_seen, novelty_score`. That's a table, not a vector space. SQLite is a single file, no server, instant transactions — ideal for frequent high-rate writes with no network latency. ChromaDB becomes useful only if we later want fuzzy semantic similarity search ("an object that looks like...") or conversational RAG — noted as a future extension, not a day-1 need. Adding complexity now for a need we don't have yet would violate the "zero ambiguity, no over-engineering" principle.

**How the novelty gauge is actually computed:**
A simple decay such as `novelty = 100 * exp(-k * encounter_count)`, calibrated so the gauge approaches 0 by roughly the 50th encounter (as originally specified). `k` is a tunable parameter, not an architectural decision.

### 2.4 Amygdala (`amygdala/`) — fast emotional reflexes

**Real role:** a deliberately simple, fast module. Its only job: if `novelty == 100` (never-seen object), it directly writes an animation order to the shared state — now realized concretely as `mini.play_move(moves.get("surprise"))` from the official emotions library — which the Brainstem plays at the next 20 ms tick. *(Confirmed scope, section 9: the official library covers all reactions for the initial build; custom recorded moves are a deliberate future extension, not part of phase 1 — see section 7.)*

**Why does this module exist separately from the Prefrontal Cortex, which could also decide to "be surprised"?**
Because the surprise reaction must be *instantaneous* (sub-100 ms) to feel credible — a human flinches before understanding why. If this decision went through the LLM (1–3 s), the robot would see the object, stay motionless for two seconds, then react — the opposite of lifelike behavior. The Amygdala therefore bypasses the LLM entirely for this case. The LLM steps in *afterward*, more slowly, to comment verbally on what the robot just saw.

**Fear, not just surprise — the same mechanism, a second trigger, higher priority**

Surprise is "something new" — fear is "something threatening," and it needs the same instant, LLM-bypassing treatment, for the same reason (a startle that waited for the LLM wouldn't read as real). Two distinct triggers feed into it, both handled entirely inside `reactions.py` so `vision.py`/`hearing.py` stay "dumb describers" per their existing role (2.2):

- **Sudden loud noise** — a lightweight amplitude-spike check in `hearing.py` (not Whisper, which only transcribes speech and is too slow/targeted for this) flags a spike in the Shared State (`sudden_noise_detected`, a timestamp). Amygdala reacts to that flag directly.
- **A recognized "scary" object** — a small hardcoded list of labels (e.g. `knife`, `scissors`) lives in `reactions.py` itself, not in perception. `vision.py` just reports "knife" like it would report "cat"; the *judgment* that a label is scary belongs to the reaction layer, not the perception layer — keeping the same separation of concerns as the rest of the architecture.
- **Confirmed content exists**: the official emotions library includes a `fear1` move (seen directly in a community reference implementation's move mapping) — same pattern as `surprise`, just `mini.play_move(moves.get("fear1"))`.

**One deliberate design choice worth flagging:** fear does **not** go through Hippocampus's novelty/habituation logic. A knife shouldn't stop being scary just because the robot has seen one 50 times, the way a cat's novelty fades (2.3) — habituation is for harmless curiosity, not threat. Fear is purely threshold-triggered every time, at least for this first build; a more nuanced threat-habituation model is a possible future refinement, not a day-1 need.

**Priority, so fear doesn't get lost among other reactions:** fear pre-empts surprise, which pre-empts idle gestures (2.1) — if a scary object appears while the robot is mid-idle-gesture or mid-surprise, fear wins and resets `last_external_command_at` like any other external target. No new mechanism needed — this is the same priority rule from 2.1, just with fear added above surprise in the ordering.

### 2.5 Prefrontal Cortex (`prefrontal_cortex/`) — deliberation

**Real role:** the only module that talks to an LLM. It builds a dynamic prompt from the current state (what's perceived + the novelty score), sends it to the chosen provider, receives a natural-language reply, and triggers speech synthesis.

**Why Ollama (local LLM) — confirmed decision**
- **Zero API cost and no network dependency** for the conversational loop, which matters since the robot will make frequent small calls continuously while running.
- **Trade-off accepted:** small local models (Llama 3.1 8B, Mistral 7B, or similar) generally have weaker personality/nuance than Gemini or Claude, and Ollama will compete for GPU/CPU time with the vision pipeline (YOLOv8/MediaPipe) and Whisper, all running on the same laptop. This is the single biggest performance risk in the whole stack now — worth measuring concretely in step 1 of the roadmap (section 7): time a full `perceive → prompt → Ollama reply` round-trip while vision inference is also running, before assuming the 1–3s latency budget in section 1.2 still holds. If Ollama contends too much with vision, a smaller/quantized model or a request-priority scheme may be needed.
- **Future mitigation already identified:** a dedicated Jetson board, later, to run YOLOv8/MediaPipe (and possibly Ollama itself) off the laptop entirely. This would directly resolve the GPU/CPU contention risk above by giving vision its own compute — noted here as the planned fix, not something to build now (see section 7, section 8).
- The architecture doesn't change at all if this needs revisiting later — the Prefrontal Cortex is the only module that knows which LLM is in use, isolated inside `ai_client.py`. Switching back to a cloud provider, or adding one as a fallback, touches nothing else.

**Why beeps first, gTTS later — refined decision**
Reachy Mini's own emotion moves already ship with built-in sounds — `play_move(..., sound=True)` plays whatever cute beep/chirp is bundled with that move, no extra code needed. **Decision: phase 1 uses only these built-in sounds for all audio feedback** — both the Amygdala's reactions (2.4) and the Prefrontal Cortex's expression, at first, are non-verbal (a move + its sound), not spoken sentences. This simplifies the early build significantly: `speech.py` in phase 1 is just "trigger the move's built-in sound," not a TTS pipeline at all. Actual spoken words (gTTS, or ElevenLabs later) are a deliberately separate, later phase — see section 7 and the updated answer to question 3 in section 9.

---

## 3. How the modules actually communicate

This is the most critical part of the project — the part where most concurrency bugs will appear if it isn't understood before coding starts.

### 3.1 The pattern: "Blackboard" (shared board)

Modules **do not talk to each other directly.** They read and write a central shared object — the **Shared State**, shown in the diagram above. This is the classic robotics pattern called **blackboard architecture**: instead of N modules calling each other in every direction (N² coupling complexity, tight-coupling bugs), each module only knows about the blackboard.

```python
# Conceptual sketch of the shared state (will live in main.py or a shared_state.py)
class SharedState:
    def __init__(self):
        self.lock = threading.Lock()
        self.current_animation_target = None   # written by Amygdala/Prefrontal, read by Brainstem
        self.last_external_command_at = None   # written whenever Amygdala/Prefrontal sets a target; read by the Brainstem's idle scheduler to know if it's safe to play a spontaneous idle gesture
        self.sudden_noise_detected = None      # timestamp, written by hearing.py's amplitude-spike check; read by Amygdala for the fear reflex (2.4)
        self.perceived_objects = []            # written by Sensory Cortex
        self.novelty_score = 0                 # written by Hippocampus
        self.last_llm_utterance = None         # written by Prefrontal Cortex
```

**Why a lock (`threading.Lock`) and not just shared variables?**
In Python, several threads can read/write the same object at once. Without a lock, you can read a "half-written" state (e.g. a list mid-update) — a classic bug called a *race condition*, hard to reproduce and debug. The lock guarantees an atomic read/write. The cost is minimal here since operations are short (no heavy computation under lock).

### 3.2 Why `threading` and not `multiprocessing` or `asyncio` alone?

This is THE concurrency decision of the project, hence the full justification:

| Option | Advantage | Drawback for us |
|---|---|---|
| **`threading`** (chosen) | Trivial memory sharing (the Shared State is a plain Python object accessible by every thread) | Python's GIL prevents true CPU parallelism — but this isn't a problem here, see below |
| `multiprocessing` | True CPU parallelism, useful if YOLOv8 saturates one core | The Shared State becomes complicated: it must be serialized across processes (`multiprocessing.Manager` or IPC queues), adding latency and complexity for a gain we haven't yet measured as necessary |
| `asyncio` alone | Very efficient for network waits (I/O bound) | The 50 Hz Brainstem plus the SDK's blocking calls don't naturally fit a pure asyncio event loop — mixing threads and coroutines badly creates more bugs than it solves for this kind of system |

**Why the GIL isn't a problem here:** the GIL prevents two threads from executing Python *bytecode* strictly simultaneously on two cores — but it's automatically *released* during waits (network I/O, blocking calls into C libraries like OpenCV/MediaPipe, `time.sleep`). Nearly all our threads spend their time *waiting*: the Brainstem waits for the next tick, the Sensory Cortex waits for the next camera frame, the Prefrontal Cortex waits for the LLM network response. This is exactly the profile where `threading` is effective in Python.

**What will use `asyncio` regardless:** the local call to Ollama in `ai_client.py`, since that's still an I/O-bound operation (a local HTTP call to the Ollama server) where `asyncio` helps — but it runs *inside its own Prefrontal Cortex thread*, never touching the Brainstem loop.

### 3.3 The exact mechanism of the Amygdala's "fast path"

Here is how the Amygdala bypasses the LLM (the most important point in the diagram):

1. Hippocampus updates `shared_state.novelty_score` after every new detection.
2. Amygdala runs in a lightweight loop (it can even live in the same thread as Hippocampus, since both tasks are fast) that checks this score.
3. If `novelty_score == 100`: Amygdala directly writes `shared_state.current_animation_target = "surprise"` — **never calling the Prefrontal Cortex.**
4. At the next tick (max 20 ms later), the Brainstem reads this target and plays the animation (via the emotions library, see 1 bis-c).

In parallel, completely independently and without blocking any of the above, the Prefrontal Cortex also receives this info (it reads the Shared State at its own, slower pace) and may decide, 1–2 seconds later, to say *"Oh, what's that thing?!"* out loud. Both reactions (instant motor, delayed verbal) coexist naturally because they only ever share a read, never a blocking call.

### 3.4 A queue (`queue.Queue`) for slow tasks

The Prefrontal Cortex must never be called *from* the Brainstem or the Amygdala directly (that would block everything waiting for the answer). Instead, we use a **thread-safe queue**:

```python
llm_request_queue = queue.Queue()
# Amygdala or Sensory Cortex, when a situation warrants it:
llm_request_queue.put({"trigger": "new_object", "context": {...}})

# In the Prefrontal Cortex's dedicated thread, in an independent loop:
while True:
    task = llm_request_queue.get()   # blocks THIS thread only, never the others
    response = ai_client.generate(task)
    speech.speak(response)
```

This is the **producer/consumer** pattern: any module can *drop off* a thinking request without ever waiting for it to be processed. Only the Prefrontal Cortex's thread waits, and that's its job — it has nothing else to do in the meantime.

---

## 4. Tech stack — decision table

| Need | Chosen option | Serious alternative | Why not the alternative (for now) |
|---|---|---|---|
| Motor control | `reachy_mini` SDK (`ReachyMini`, `goto_target`/`set_target`) | Raw low-level control (bare protobuf/gRPC) | The SDK exists precisely to avoid reinventing the transport layer — no reason to bypass it |
| Discrete emotion animations | Official `reachy-mini-emotions-library` via `RecordedMoves` | Hand-authored keyframe animations | The library already covers this need — building our own duplicates existing, tested work |
| Conversational LLM | **Ollama (local LLM)** | Gemini, Claude API | Zero cost, no network dependency; accepted trade-off: weaker nuance on small models + GPU contention with vision (see 2.5) |
| Real-time vision | MediaPipe + YOLOv8 | Cloud VLM (GPT-4V, Gemini Vision) per frame | Latency and cost incompatible with continuous 5–30 Hz operation |
| STT | Local Whisper | Cloud STT API | Continuity (permanent listening) without per-second billing |
| TTS | **Phase 1: built-in move sounds (beeps).** Phase 2+: gTTS | ElevenLabs, local TTS (Coqui, Piper) | Beeps need zero extra code (bundled with library moves) and get the loop working end-to-end first; spoken words are a deliberately separate later phase (see 2.5, section 9 Q3) |
| Fear/startle content | Official `reachy-mini-emotions-library`, `fear1` move | Custom recorded fear move | Confirmed to already exist in the library (community reference implementation), same pattern as `surprise` — no need to record anything for v1 |
| Structured memory | SQLite | ChromaDB / Postgres | Current need = a simple table, no vector search, no server to manage |
| Concurrency | `threading` + `queue` | `multiprocessing`, pure `asyncio` | The project's I/O-bound profile favors `threading` despite the GIL; `asyncio` reserved for the internal LLM call |
| App scaffolding | **`reachy-mini-app-assistant create` (default template)** | `--template conversation` | The conversation template didn't scaffold cleanly for this setup; default template still respects the official "never hand-create the folder" rule |
| App flavor | Python app (on-robot / on-laptop) | JS/Web app (HF Space, WebRTC) | Reachy Alive needs continuous local compute (vision, audio, real-time loop, local DB) — exactly the documented exception case for choosing Python over the default JS recommendation |
| Idle gesture content (yawn, stretch, look around) | `reachy-mini-dances-library` (idle/subtle category) + procedural look-around (`goto_target` + `create_head_pose`, per Pollen's own `sweep_look.py` pattern) | Fully custom recorded moves for everything | The dance library's idle category and the procedural look-around pattern already exist and are tested; custom moves reserved for whatever (likely yawn/stretch) turns out missing after checking `list_moves()` |
| Robot connectivity | **Wireless, streamed mode** (WiFi to CM4, compute on laptop) | Wireless local-only, Lite/USB | Confirmed hardware is Wireless; streamed mode keeps full laptop compute, matching the original architecture almost unchanged (see 1 bis-f) |

---

## 5. File structure — role of each file

**Important caveat vs the original draft:** the top-level scaffold (pyproject.toml, entry point, `static/` folder if a web UI is ever bundled) will be generated by `reachy-mini-app-assistant create` (default template, see 1 bis-h), not hand-written. The structure below describes our **cognitive modules**, which will be placed inside whatever package layout the assistant generates. Since we're using the default (minimal) template rather than `conversation`, there's nothing pre-existing to reconcile against — our five modules are added cleanly.

```text
reachy_alive/                      # package generated by reachy-mini-app-assistant, then extended
    ├── __init__.py
    ├── main.py                    # (A) see 5.1
    │
    ├── brainstem/
    │   ├── engine.py               # (B) the 50Hz decision loop + thread management; calls ReachyMini
    │   ├── reflexes.py             # (C) pure functions: position computation (sine wave, interpolation), respects safety limits (1 bis-e)
    │   └── idle_behaviors.py       # (C2) spontaneous idle scheduler (yawn/stretch/look-around timer + priority vs external targets, see 2.1)
    │
    ├── sensory_cortex/
    │   ├── vision.py                # (D) camera capture + MediaPipe/YOLOv8 inference
    │   └── hearing.py               # (E) mic capture + Whisper inference + amplitude-spike check for sudden noise (2.2)
    │
    ├── hippocampus/
    │   ├── database.py              # (F) SQLite connection, CRUD for encountered objects
    │   └── habituation.py           # (G) novelty_score computation from the DB
    │
    ├── amygdala/
    │   └── reactions.py             # (H) "novelty==100 -> surprise" and "scary object / sudden noise -> fear" (2.4), calls play_move()
    │
    └── prefrontal_cortex/
        ├── prompt_builder.py        # (I) formats the dynamic prompt from the Shared State
        ├── ai_client.py             # (J) local call to Ollama (see 2.5)
        └── speech.py                # (K) phase 1: trigger the move's built-in sound; phase 2+: gTTS for spoken words (2.5)
```

### 5.1 `main.py` — the only file that "knows everything"

The single entry point. Its exclusive job:
1. Instantiate the `SharedState` (the blackboard object from 3.1)
2. Instantiate the `llm_request_queue` (3.4)
3. Start one thread per module (Brainstem, Sensory Cortex, Hippocampus+Amygdala, Prefrontal Cortex), passing them references to the Shared State and the queue
4. Handle clean shutdown (Ctrl+C → signal all threads to terminate cleanly; per the official guide, also call `safelyReturnToPose`-equivalent behavior on exit so the robot returns to a safe rest pose rather than freezing mid-gesture)

**Key design rule:** no file imports a sibling module directly (e.g. `reflexes.py` never imports `vision.py`). Every module only depends on `SharedState`, and the Prefrontal Cortex additionally on the queue. This is what makes each brick testable in isolation — you can test `hippocampus/habituation.py` with a fake `SharedState`, without launching the whole robot.

### 5.2 Inter-file communication table

| File | Reads from Shared State | Writes to Shared State | Other communication |
|---|---|---|---|
| `engine.py` (Brainstem) | `current_animation_target` | nothing (Brainstem executes, it doesn't decide) | Calls `reachy_mini.ReachyMini` directly |
| `reflexes.py` | nothing (pure functions, receives parameters) | nothing | Called only by `engine.py` |
| `idle_behaviors.py` | `current_animation_target`, `last_external_command_at` | `current_animation_target` (only when idle and no recent external command) | Calls `mini.play_move(...)` from the dances library, or `goto_target` for procedural look-around |
| `vision.py` / `hearing.py` | nothing | `perceived_objects`; `hearing.py` also writes `sudden_noise_detected` | — |
| `database.py` / `habituation.py` | `perceived_objects` | `novelty_score` | Reads/writes SQLite |
| `reactions.py` (Amygdala) | `novelty_score`, `sudden_noise_detected` | `current_animation_target` (on surprise or fear) | Calls `mini.play_move(moves.get(...))`; holds the small "scary object" label list |
| `prompt_builder.py` | `perceived_objects`, `novelty_score` | nothing | — |
| `ai_client.py` | nothing | `last_llm_utterance` | Puts into / reads from `llm_request_queue`; local call to Ollama |
| `speech.py` | `last_llm_utterance` | nothing | Phase 1: triggers the move's built-in sound; phase 2+: calls the TTS provider |

This table is the exact spec of who touches what — at coding time, each file can be written by looking only at its own row.

---

## 6. The full lifecycle of an event (worked example)

To make all of this concrete, here's what happens, second by second, the first time the robot sees a cat:

1. **t = 0 ms** — `vision.py` detects an object via YOLOv8, writes `perceived_objects = ["cat"]` to the Shared State
2. **t = 5 ms** — `habituation.py` (Hippocampus thread, running its own fast loop) sees the update, queries SQLite: "cat" doesn't exist → first encounter → computes `novelty_score = 100`, writes it to the Shared State
3. **t = 8 ms** — `reactions.py` (Amygdala, same or a neighboring loop) sees `novelty_score == 100`, writes `current_animation_target = "surprise"`
4. **t = 20 ms** (next Brainstem tick) — `engine.py` reads `current_animation_target`, triggers `mini.play_move(moves.get("surprise"))` → **the robot flinches less than 30 ms after "seeing" the cat**
5. **In parallel, t = 8 ms** — `reactions.py` also drops a task into `llm_request_queue`: `{"trigger": "new_object", "object": "cat", "novelty": 100}`
6. **t = 8 ms → 1500 ms** — the Prefrontal Cortex thread, which was waiting on the queue, picks up the task; `prompt_builder.py` builds a prompt like *"You just saw a cat for the first time, you're curious and amazed, react in one sentence"*; `ai_client.py` sends it to the LLM
7. **t ≈ 1500 ms** — the reply arrives ("Ohh, what is this little four-legged creature?!"), written to `last_llm_utterance`
8. **t ≈ 1500 ms** — `speech.py` synthesizes and plays the audio

Perceived result: the robot flinches *instantly* upon seeing the cat, then, a second and a half later — the natural time it takes to "think" — it comments on what it just saw. That's exactly the behavior we're after, and it's proof the layered architecture works: no slow step ever delayed the fast reaction.

---

## 7. Development roadmap (in order)

The order is designed so each step is testable on its own, without depending on later steps — consistent with a brick-by-brick approach.

0. **Scaffold the app** with `reachy-mini-app-assistant create reachy_alive <path> --publish` (default template). Skim the `reachy_mini_conversation_app` reference example for AI-integration patterns, but build `ai_client.py`/`speech.py` from scratch as planned in 2.5.
1. **Brainstem alone** — make the robot breathe/move in the 50 Hz loop with `reflexes.py` hard-coded, no other module. Validates the real-time loop and the `ReachyMini` connection over WiFi (streamed mode), and confirms `goto_target()`/`set_target()` behave as expected. **Also measure camera round-trip latency here** (see 1 bis-f) — first real data point on whether streamed Wireless mode needs any tuning for tracking smoothness. **Also check `moves.list_moves()`** on both the emotions and dances libraries to confirm what idle/yawn/stretch content actually exists before wiring `idle_behaviors.py` (see 2.1).
1 bis. **Idle variety** — add `idle_behaviors.py`: the timer-based scheduler, the dance-library idle moves, and the procedural look-around. Testable alone, without the rest of the cognitive stack, since it only depends on the Shared State's `last_external_command_at` field.
2. **Shared State + Sensory Cortex (vision only)** — wire up the camera, log detections, without acting on them yet.
3. **Hippocampus** — wire up SQLite, validate that the novelty score is computed and decays correctly on repeated encounters (testable without the robot).
4. **Amygdala + fast path** — connect the novelty score to a "surprise" reaction using `mini.play_move(moves.get("surprise"))` from the official emotions library. **Also wire the fear reflex here** (2.4): the amplitude-spike check in `hearing.py`, the scary-object label list in `reactions.py`, and `mini.play_move(moves.get("fear1"))`. First moment the robot "reacts" to what it sees and hears.
5. **Prefrontal Cortex in isolation** — test `prompt_builder.py` + `ai_client.py` from the command line, without the robot, to validate the personality prompt before wiring it live.
6. **Full integration + non-verbal expression** — connect everything, add Whisper for listening, test the full cycle from section 6. **Audio output in this phase is built-in move sounds only** (`play_move(..., sound=True)`) — no spoken words yet, per the phased TTS decision in 2.5.
7. **Personality refinement** — iterate on the prompt, idle animations, novelty thresholds.
8. **(Future, out of scope for now)** Record custom moves to extend beyond the official emotions library, add spoken TTS (gTTS, then possibly ElevenLabs) once non-verbal expression works well, consider a dedicated Jetson to offload YOLOv8/MediaPipe (and possibly Ollama) from the laptop if GPU contention (section 8) turns out to be a real bottleneck, and/or a configuration web page (voice, personality settings) — all deliberately deferred per section 9.

---

## 8. Points of vigilance

- **The Shared State lock must never wrap a slow operation** (e.g. never a network call under `lock`). Otherwise we recreate exactly the problem we're trying to avoid — the Brainstem would end up waiting to access a variable.
- **`ReachyMini` should be called from a single thread** (the Brainstem's). Confirm in the SDK docs whether concurrent calls from multiple threads are safe before step 1 — the official guide doesn't state this explicitly either way.
- **Respect the documented safety limits (1 bis-e)** by design in `reflexes.py`, even though the SDK auto-clamps — don't rely on clamping to catch an out-of-range animation.
- **Ollama will compete with YOLOv8/MediaPipe/Whisper for the same laptop's GPU/CPU.** This is now the top performance risk in the stack (see 2.5) — measure it early rather than assuming the 1–3s LLM latency budget from section 1.2 still holds once vision is also running. **A dedicated Jetson later is the identified mitigation** for this exact risk (section 7, step 8) — not needed to start, but worth keeping in mind if the laptop measurement in step 1 looks bad.
- **Streamed Wireless mode adds network latency to every camera frame**, on top of whatever Ollama/vision contention adds. Measure both in step 1 before tuning the tracking loop.
- **Idle gestures must always yield to real reactions, and fear must always yield to nothing.** The priority order is fear > surprise > idle (2.1, 2.4) — an idle yawn firing mid-surprise, or a surprise reaction overriding a fear response, would break the illusion of "alive" faster than no reaction at all.
- **The noise-spike threshold needs real tuning, with a cooldown.** A startle reflex that fires on every dropped object or door close will read as broken, not alive — plan to tune the RMS threshold empirically in step 4, and add a short cooldown after each fear trigger so it doesn't re-fire continuously on a sustained loud sound.
- **Don't assume yawn/stretch exist by name in the official libraries** — verify with `list_moves()` in step 1 of the roadmap before designing `idle_behaviors.py` around names that might not exist.
- **The LLM/TTS provider choice is still reversible by design** (isolated in `ai_client.py`/`speech.py`) — if Ollama's latency or quality turns out to be a blocker, switching to a cloud provider later doesn't touch anything else.

---

## 9. Open questions — please answer before coding

Following the official `AGENTS.md` convention (clarifying questions live directly in `plan.md`, with answer fields, and coding waits until they're answered):

1. ~~**Hardware in hand:** Lite or Wireless?~~
   **Answer: Wireless (CM4, WiFi)** — resolved in 1 bis-f, running in streamed mode with compute on the laptop.

2. ~~**LLM provider:**~~
   **Answer: Ollama (local LLM)** — resolved in 2.5 and the tech stack table.

3. ~~**TTS provider:**~~
   **Answer: phase 1 uses only the built-in move sounds (beeps) from the emotions library — no spoken words yet. gTTS is confirmed as the choice for phase 2+, once spoken conversation is wanted** — resolved in 2.5 and the tech stack table.

4. ~~**Emotions library scope:**~~
   **Answer: use `reachy-mini-emotions-library` for now, plan custom recorded moves later.** Practical implication: `reactions.py` calls `moves.get(...)` from the official library for every reaction in phase 1 (section 7). Recording custom moves is out of scope for the initial build — noted as a phase-8+ extension once the base personality works, using Pollen's own recording tooling (not something to design now).

5. ~~**Web UI:**~~
   **Answer: a Hugging Face Space page will exist to *present/showcase* the project, but there is no embedded control UI for now** (no web page to tweak the robot's behavior). A configuration UI (e.g. for voice settings) is a possible future addition, explicitly deferred. Practical implication: the default `reachy-mini-app-assistant` scaffold's `static/` folder, if generated, stays essentially unused for now — it's not part of the section 7 roadmap. The HF Space presentation page is a separate, later concern (packaging/publishing), not part of the cognitive architecture in this document.
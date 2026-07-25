# Project Plan: Reachy Alive

## 1. Context and Objective
The "Reachy Alive" project aims to transform a Reachy Mini into a robotic entity endowed with the illusion of life, drawing inspiration from the cognitive architecture of a "near-human" (a curious child). 
The goal is to move away from the traditional "slave" robot paradigm (which waits for an explicit command to move) toward a robot that truly "lives" in its environment: it breathes continuously, marvels at novelty, becomes habituated to everyday objects, and communicates naturally using an LLM. The system will initially run on a local computer (ThinkPad) communicating with the robot over the network.

---

## 2. Cognitive Architecture (Software Organs)

To prevent slow AI reasoning latency from freezing the robot's fast physical movements, the codebase is segmented into modules inspired by regions of the human brain.

### A. Brainstem & Cerebellum (Motor Reflexes)
*   **Role:** The survival loop and physical animation system of the robot. It handles the continuous "breathing" (perpetual Idle motion), face-tracking, and safe execution of motor animations.
*   **Technologies:** An asynchronous Python thread (running at 50 Hz), the `reachy-sdk` library, and mathematical formulas (`numpy`).
*   **Why this stack?** Motor control demands real-time execution and strict safety. Using an independent mathematical Python loop separate from the LLM guarantees that the robot never stops moving, even if the internet connection drops.

### B. Sensory Cortex (Perception)
*   **Role:** Acts as the robot's eyes and ears. This module converts raw audio and video streams into text-based concepts usable by the rest of the system ("I see a cat", "I hear 'hello'").
*   **Technologies:** `YOLOv8` or `MediaPipe` for fast computer vision. `OpenAI Whisper` (or a local equivalent) for Speech-to-Text.
*   **Why this stack?** These models are lightweight and highly optimized. They run smoothly on a ThinkPad's CPU or integrated GPU without hogging system resources.

### C. Hippocampus (Memory and Habituation)
*   **Role:** Stores the history of visual encounters and manages the "Novelty Gauge". It allows the robot to get used to its environment (e.g., marveling the first time it sees a tree, but ignoring it on the 100th encounter).
*   **Technologies:** `SQLite` (to count object occurrences), optionally paired with `ChromaDB` (for storing richer episodic memories via Retrieval-Augmented Generation / RAG).
*   **Why this stack?** LLMs like Gemini are stateless and amnesic by default. A lightweight local database fixes this flaw cleanly without wasting unnecessary API tokens, maintaining persistent memory on disk.

### D. Amygdala (Emotion and Fast Alert)
*   **Role:** Triggers instinctive emotional reactions *before* the LLM finishes thinking. If the Hippocampus reports a Novelty score of 100/100, the Amygdala instantly sends a startle/surprise command to the Cerebellum.
*   **Technologies:** Standard Python conditional logic (`if / else`) communicating via thread-safe shared state variables.
*   **Why this stack?** Emotion must be instantaneous to be believable. Simple hardcoded rules deliver near-zero latency (a few milliseconds), creating a convincing illusion of life.

### E. Prefrontal Cortex (Reflection and Personality)
*   **Role:** The higher intelligence. It gathers observations from the Sensory Cortex and the novelty score from the Hippocampus, then constructs a "Dynamic Prompt" to make the robot speak with the personality of a curious child.
*   **Technologies:** `Gemini API` (Cloud Model), and a Text-to-Speech (TTS) engine for the voice.
*   **Why this stack?** Gemini offers high-level semantic reasoning capabilities. Offloading this to a Cloud API provides maximum intelligence without overburdening the local laptop. The TTS engine gives a physical voice to the generated text.

---

## 3. Target Directory Structure

Respecting the official standard imposed by Pollen Robotics (with the web frontend and `pyproject.toml` at the root), here is how the cognitive architecture translates into python packages and modules:

```text
reachy_alive_project/
├── index.html                 # Frontend: Optional web UI (camera preview, settings)
├── style.css                  # Frontend: Visual styling
├── pyproject.toml             # Dependencies (reachy-sdk, openai, opencv, etc.)
├── README.md                  # Project overview
├── plan.md                    # (This file)
│
└── reachy_alive/              # 🧠 MAIN PYTHON PACKAGE
    ├── __init__.py
    ├── main.py                # Entrypoint: Initializes ReachyMiniApp and runs all organs in parallel
    │
    ├── brainstem/             # Cerebellum (Fast Loop)
    │   ├── __init__.py
    │   ├── engine.py          # The 50 Hz clock / loop manager
    │   └── reflexes.py        # Mathematical motions (Idle, face tracking)
    │
    ├── sensory_cortex/        # Perception (Senses)
    │   ├── __init__.py
    │   ├── vision.py          # YOLOv8 / MediaPipe integration
    │   └── hearing.py         # Microphone capture & Whisper
    │
    ├── hippocampus/           # Memory
    │   ├── __init__.py
    │   ├── database.py        # SQLite / ChromaDB connection
    │   └── habituation.py     # Novelty gauge calculations
    │
    ├── amygdala/              # Fast emotional responses
    │   ├── __init__.py
    │   └── reactions.py       # Rules (e.g., If novelty == 100 -> Trigger 'Surprise' animation)
    │
    └── prefrontal_cortex/     # LLM Intelligence
        ├── __init__.py
        ├── prompt_builder.py  # Assembles context (vision + memory) for the LLM
        ├── gemini_client.py   # Cloud API communication
        └── speech.py          # Text-to-Speech synthesis
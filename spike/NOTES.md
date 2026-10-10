# Spike: senses

What each sense actually gives on the robot, before designing anything.
Throwaway branch, never merged: these answers go into the PR of each sense.

## Inertial unit (2026-10-05, Wireless robot)

- 50 Hz, very clean at rest (norm 9.78 m/s², std 0.02). None in simulation
  and on the Lite.
- Mounted in the head: gravity moves between axes with the head pose.
- Bump (table, head): the norm deviates 5-9 m/s² for 1-2 samples, with
  little rotation.
- Lifted: strong rotation for seconds. Looks like head motion, so not
  detectable for now.
- Breathing: deviation under 1 m/s², gyro bumps every 4 s.
- A move (sneezing) deviates as much as a bump: the robot feels itself.
- First fact: bump, a threshold on the norm's deviation (somewhere around
  2-3 m/s²), ignoring the moves the robot plays. The norm doesn't change
  when the head tilts; a single axis does.

## Touch: antennas (2026-10-05)

- Present position is measured. Order: 0 = right, 1 = left (real robot;
  MuJoCo uses the opposite order).
- Still: error at rest ~0.2-0.3 deg (a constant offset); pushes 7-16 deg.
- Swaying like breathing: the left antenna lags its target by ~80 ms, error
  within ±3 deg, a sinusoid. Comparing to the target from 80 ms earlier
  drops it from 2.65 to 1.14 deg (checked on sway_check).
- The right antenna moves in jerks while swaying, error up to 6-10 deg with
  nothing touching it: as large as a push. Its best delay is 100-160 ms,
  and it stays around 3-4 deg. A slight catch is felt by hand and heard,
  motor side.
- Pollen (Discord): antenna oscillation is known; the 10 deg offset is
  their fix (our NEUTRAL_ANTENNAS_RAD). Friction varies per unit; the
  troubleshooting page suggests P=180 (then D=10) on motors 10, 17, 18 in
  hardware_config.yaml. A robot-wide setting: the app must work with the
  defaults, which is what users have.
- The sense needs the commanded target: how does it get it from the
  control loop? Main design question for the touch PR.
- Users' robots will differ: a fixed threshold tuned on one antenna may
  misfire elsewhere. Option for later: learn each antenna's normal error
  while breathing, and flag what stands out from it.
  - Option B (target from the daemon) is blocked in 1.11: /api/state/full
  computes the target, but its response model (FullState) has no target
  field, so FastAPI drops it. Known: pollen-robotics/reachy_mini#1457.
  Back to option A: the RobotController publishes the target it sends.

## Hearing (2026-10-05, from the laptop over WebRTC)

- Stereo float32, 16 kHz, already processed by the mic chip: no spatial
  cue in the audio. Raw mics need the 6-channel firmware.
- The background moves between -30 and -60 dBFS (automatic gain or
  ambient): a fixed dB threshold won't work. Detect a jump above the recent
  background instead (claps: +50 dB within one 20 ms window).
- Speech rises more gradually and lasts; claps are one window wide.
- The robot hears itself: sneezing reaches -20 dBFS and is even flagged as
  speech. Echo cancellation doesn't remove it from what we get.
- DoA: updates mostly on speech and holds the last value otherwise, ~1 s
  late after a clap. Reliable for voices (front 85-100 deg), not for brief
  sounds: the sudden-noise fact carries no direction. Behind reads as front
  (~90 deg).
- DoA angles are in the robot's frame: the robot's left. During the spike
  I clapped on my own left, facing the robot, and it read right. Every
  direction stored in SharedState must say its frame.
- From the laptop, get_DoA() is None (it reads the chip over USB); use the
  daemon's /api/state/doa there. On the robot, get_DoA() works directly.
- A second client (try-move) cut the recording's audio stream after
  11.7 s. Over WebRTC only? The hearing sense must be tried on the robot.

## Hearing, second round (2026-10-09, during the sense's PR, laptop over WebRTC)

Recorded with `hearing/levels_record.py`: one loudness level per 20 ms
stretch, the detector's verdict, and the chip's automatic gain read every
0.5 s. No sound kept. Data: `hearing/levels_speech.csv` (+ `.png`); the
controlled recording went into the PR's tests (`hearing_levels.csv`).

- Over WebRTC, chunks are always 320 stereo samples (20 ms, Opus frames),
  with ~1 s of nothing while the connection opens, then lone gaps (network
  jitter). Chunk size on the robot itself (`alsasrc`) not measured.
- The mic chip (XMOS XVF3800) has automatic gain on (`PP_AGCONOFF = 1`),
  readable through the daemon: `/api/audio/config/parameter/PP_AGCGAIN`
  (a factor). It climbs in silence (+15 dB after a minute) and drops within
  ~0.3 s once someone talks. Absolute levels are unreliable: a floor at
  -16 dBFS was tried and dropped.
- The jump above the background doesn't separate voice from knocks: the
  start of a sentence jumps 26-37 dB (more in a quieter room), claps 39-60,
  a mouse put down hard 37-45.
- Abruptness does, so far: the rise within one 20 ms stretch is 34-46 dB for
  claps, 37-38 for a mouse put down hard, 17-21 gently, 20 for a knuckle
  knock (in two steps), 26 for someone shifting on a chair, and 2-16 at the
  start of a sentence. Not yet checked on a door slammed close by.
- A mouse on the robot's table or on another table reads the same: the
  sound comes through the air, not the table.
- People get used to repeated sounds: of three claps in a row, only the
  first should startle. Habituation (a loud sound is expected within 10 s
  of the last, unless 10 dB louder) does it on the first two recordings. In
  `levels_speech`, talking counted as loud sounds: the first clap, 6 s
  later, was expected, and the second, 20 dB louder, startled. Another
  reason for voice to be a feature of the sound.
- Perceiving isn't reacting: whether a voice or a bang should startle the
  robot depends on context (asleep, sees someone, expects it). The sense
  describes the sound (how loud, how abrupt, voice or not); reflexes decide.

## Vision (2026-10-05)

- 1280x720 frames, analysed at 320x180 (one pixel in four each way).
- Cost, laptop vs robot: face detection 1.6 vs 32 ms per frame; the script
  used 44% vs 63% of one core. On the robot, at 10 frames analysed per
  second (partly the script's own full-frame duplicate check). Faces at
  5 Hz would cost ~16% of one core of the CM4.
- Faces: no false positive in an empty room, found at ~1 m, still found
  while the head breathes. Face width not measured (script bug: bbox is
  x, y, w, h): max distance still open.
- Motion (pixels changed by more than 15 gray levels): 0% with the head
  still in an empty room, 5-25% when someone walks by, but up to 12% from
  breathing alone (sub-pixel shifts along contrasted edges). Naive frame
  differencing is unusable while the robot breathes.
- The camera adjusts its exposure on its own: a global brightness change
  also reads as motion.

## Across senses

- All three senses so far feel the robot's own activity (moves, antenna
  motion, its own sounds). They all need to know what the robot is doing:
  a fact written by the RobotController (efference copy)?

## Conclusions

| Sense | First fact | Main difficulty |
|---|---|---|
| Inertial unit (in the head) | Bump | Its own moves shake it as much as a tap |
| Antennas | Push | Permanent sway (solved by the delayed target); units differ |
| Hearing | Sudden noise, no direction | Moving background (relative threshold); hears itself; try on the robot |
| Vision | Faces (motion later) | Permanent breathing makes the whole image "move" |

Decided from the spike:
- Order of the senses: inertial unit, antennas, hearing, vision.
- Every sense needs to know what the robot is doing (efference copy). First
  version: a fact "a move is playing", written by the RobotController.
  Suppression is enough for the inertial unit and hearing at first; the
  antennas and vision need prediction, since breathing never stops.
- The same fact will give reactions their context (e.g. sneezing + antenna
  held = it holds back the sneeze).
- During a move, the antennas are the reliable channel to interrupt the
  robot: a tap on the head can't be told apart from its own sneeze yet.
- Senses run in their own threads: the control loop blocks during moves.
- Laptop numbers say nothing about the robot: measure the cost on the CM4.

Still open:
- How far away a face is still found (the spike's face width was wrong).
- How vision tells breathing apart from real motion (prediction, global
  shift, or local change).
- Hearing on the robot itself, without WebRTC (chunk size, gain).
- Abruptness on a door slammed close by, and on a sound split across two
  stretches.
- How reliable and how late the chip's voice detection (`speech_detected`)
  is, as a feature of the sound.
- Predicting the head's acceleration from its commanded trajectory, to feel
  a tap during a move.
- The right antenna: gearbox or a screw too tight (Pollen's checks).
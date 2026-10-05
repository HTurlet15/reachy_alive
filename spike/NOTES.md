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

## Across senses

- All three senses so far feel the robot's own activity (moves, antenna
  motion, its own sounds). They all need to know what the robot is doing:
  a fact written by the RobotController (efference copy)?
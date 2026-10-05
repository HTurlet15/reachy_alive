# Spike: senses

## Inertial unit (2026-10-05, Wireless robot)

- 50 Hz, very clean at rest (norm 9.78 m/s², std 0.02). None in simulation.
- Mounted in the head: gravity moves between axes with the head pose.
- Bump (table, head): norm deviates 5-9 m/s² for 1-2 samples, little rotation.
- Lifted: strong rotation for seconds; looks like head motion, so not
  detectable for now.
- Breathing: deviation < 1 m/s², gyro bumps every 4 s.
- A move (sneezing) deviates as much as a bump: the robot feels itself.
- First fact: bump, threshold on the norm's deviation (somewhere 2-3 m/s²),
  ignoring moves the robot plays.

  ## Touch: antennas (2026-10-05)

- Present position is measured. Order: 0 = right, 1 = left (real robot).
- Still: error at rest ~0.2-0.3 deg (constant offset); pushes 7-16 deg.
- Swaying like breathing: left antenna lags its target by ~80 ms, error
  within +-3 deg, a sinusoid. Comparing to the target from 80 ms earlier
  should cancel most of it.
- Right antenna moves in jerks while swaying, error up to 10 deg untouched:
  as large as a push. Mechanical friction? To check.
- The sense needs the commanded target: how does it get it from the control
  loop? Main design question for the touch PR.
  - Right antenna: slight catch felt by hand and heard, motor side. Likely a
  hardware defect of this unit; reported to Pollen with sway.png.
- Users' robots will differ too: a fixed threshold tuned on one antenna may
  misfire elsewhere. Option for later: learn each antenna's normal error
  while breathing, and flag what stands out from it.
  - Delayed target checked on sway_check: left antenna error drops from
  2.65 to 1.14 deg comparing to the target from 80 ms earlier. Right
  antenna needs 100-160 ms and stays around 3-4 deg (its jerks).
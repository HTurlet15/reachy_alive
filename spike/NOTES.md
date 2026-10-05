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
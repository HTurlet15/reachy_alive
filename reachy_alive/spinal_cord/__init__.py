"""From a proposal to the robot, like the body's spinal cord.

Decision-makers propose; the ActionSelector (brain/basal_ganglia/) chooses a
move; the MovePlayer (brain/cerebellum/) turns it into a command each tick
(commands.py); the RobotController executes it in the control loop, and is
the only part that drives the robot.
"""

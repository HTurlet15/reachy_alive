"""From a proposal to the robot, like the body's spinal cord.

Decision-makers propose; the ActionSelector (brain/basal_ganglia/) picks one
proposal each tick and turns it into a command (commands.py); the
RobotController executes it in the control loop, and is the only part that
drives the robot.
"""

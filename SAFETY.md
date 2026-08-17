# Safety policy

This repository can send motion commands to a physical AgileX Piper robot.
It is research and integration software, not a certified functional-safety
system and not a replacement for the manufacturer's safety controls.

## Before connecting hardware

1. Read the robot, controller, gripper, and emergency-stop manuals.
2. Verify that the physical emergency stop works before starting this software.
3. Clear and isolate the robot workspace. Keep people, cables, and loose
   objects outside the full reachable volume.
4. Confirm the arm, gripper, firmware, CAN interface, joint order, units, and
   limits match the selected configuration.
5. Keep an operator at the emergency stop. Do not run unattended.

## First motion

- Start with `motion_speed_percent: 30` or lower.
- Test one joint at a time with a small displacement.
- Validate direction and zero pose before multi-joint motion.
- Test the gripper without an object first.
- Stop immediately on unexpected direction, vibration, collision, stale
  feedback, communication loss, or limit disagreement.

Software limit checks and clipping do not provide collision avoidance,
workspace monitoring, force limiting, or a safety-rated stop.

## Recorded actions and playback

MCAP and action data can cause immediate physical motion. Before playback:

- inspect the recording and test it in simulation;
- verify `joint1` through `joint6` use radians;
- verify `gripper` is the total finger opening in meters (`0..0.105`);
- never replay legacy millimeter values without explicit conversion;
- begin at reduced speed in an empty workspace.

## Connection lifecycle

Follower mode moves to the configured `initial` position after connection and
to `reset` before normal disconnection. After reaching reset, the driver
disconnects CAN without calling `DisablePiper()`, so the robot may remain
torque-enabled. A failed reset still causes CAN disconnection and reports
failure. The operator must understand and manage the resulting hardware state.

## Security and incident reporting

Do not commit robot addresses, credentials, private recordings, calibration
secrets, or personally identifiable images. Report software vulnerabilities
through this repository's GitHub private vulnerability reporting page. For an
active hardware hazard, use the physical emergency stop first.

## Disclaimer

The software and assets are provided "AS IS", without warranties or conditions
of any kind. Users are responsible for risk assessment, supervision, regulatory
compliance, and any personal injury or equipment damage arising from use.

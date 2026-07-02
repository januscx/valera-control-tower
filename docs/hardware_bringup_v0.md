# Hardware Bring-up v0

## Goal

Define the next phase after camera/evidence validation: safe hardware readiness
probing for SO-ARM 101 and the tracked Valera base.

Hardware Bring-up v0 is a readiness and safety phase. It does not include robot
movement, arm control, torque enablement, grasp, release, base movement, or
actuator calls.

## Current verified status

- CI green
- stable non-hardware smoke green
- live camera probe works
- ArUco `DICT_4X4_50` marker id `7` detected
- event/evidence/dashboard pipeline works
- physical demo runner completed with operator confirmations
- no real arm/base movement has been validated

## Not verified yet

- SO-ARM 101 connection
- SO-ARM 101 read-only state
- SO-ARM 101 safe torque-disabled mode
- tracked base connection
- tracked base read-only status/heartbeat
- base movement
- arm movement
- real grasp/release

## Safety rules

- default mode is fail-closed
- probe-only before motion
- read-only before write
- torque/motion disabled by default
- no actuator calls from demo runners
- explicit operator opt-in required for any future hardware access
- emergency stop / physical power cut must be available before any motion test
- no autonomous motion in Hardware Bring-up v0

## Hardware inventory checklist

- [ ] USB devices documented
- [ ] serial devices documented
- [ ] `/dev/tty*` devices documented
- [ ] `/dev/video*` devices documented
- [ ] user groups and permissions documented
- [ ] power state documented
- [ ] physical emergency stop / power disconnect available and documented
- [ ] camera placement documented
- [ ] arm mechanically safe pose documented
- [ ] base lifted/off-ground or tracks disabled before any future movement test

## Hardware Inventory v0

Purpose: collect a local, read-only snapshot of connected hardware so follow-up
PRs can plan SO-ARM 101 and tracked base probes without guessing which devices
exist on the machine.

Run:

```bash
python3 scripts/collect_hardware_inventory.py
```

Outputs are generated under ignored paths:

- `tmp/hardware-inventory/latest.json`
- `tmp/hardware-inventory/latest.md`

The inventory records:

- timestamp, hostname, current user, groups, platform, and kernel
- `/dev/video*`, `/dev/tty*`, `/dev/serial/by-id/*`, and `/dev/serial/by-path/*`
- optional `lsusb`, `lspci`, and `v4l2-ctl --list-devices` output when available
- availability of `lsusb`, `v4l2-ctl`, `udevadm`, `python3`, and `lspci`
- Python version, whether `cv2` imports, and whether `cv2.aruco` is available
- heuristic-only candidate notes for `possible_orbbec_camera`,
  `possible_so_arm_serial`, and `possible_tracked_base_serial`

The inventory explicitly does not:

- open cameras
- capture frames
- open serial ports
- send serial commands
- enable torque
- move the robot
- control the arm
- call actuators
- run the live camera probe or physical demo

Use `latest.md` for human review and `latest.json` for exact device paths and
command output. Follow-up PRs should treat all candidate labels as possible
matches only, then add separate probe-only code with explicit safety notes.

## SO-ARM 101 probe checklist

Probe-only:

- [ ] identify connection/interface
- [ ] identify required runtime/library
- [ ] read model/config if possible
- [ ] read joint/state if possible
- [ ] verify torque disabled if applicable
- [ ] do not send movement commands

## Tracked base probe checklist

Probe-only:

- [ ] identify connection/interface
- [ ] identify controller/protocol
- [ ] read status/heartbeat if possible
- [ ] verify movement commands are not sent
- [ ] keep tracks disabled/off-ground for future tests

## Acceptance criteria for Hardware Bring-up v0

- hardware inventory documented
- SO-ARM connection path identified
- base connection path identified
- no movement performed
- no actuator calls performed
- next PR slices defined

## Follow-up PR slices

- PR A: hardware inventory script/report, read-only
- PR B: SO-ARM probe adapter, no torque/motion
- PR C: tracked base probe adapter, no movement
- PR D: hardware safety gate model
- PR E: first controlled motion test plan, docs only, not execution

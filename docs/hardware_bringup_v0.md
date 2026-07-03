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
- SO-ARM Readiness Phase 1 is metadata-only and fail-closed by default
- SO-ARM Readiness Phase 2 is permissions/operator-readiness only and does not
  open serial
- SO-ARM Readiness Phase 3 defines an adapter contract skeleton with a
  metadata-only SO-ARM adapter and still does not open serial

## Not verified yet

- SO-ARM 101 protocol/library identity
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

## Valera inventory snapshot - 2026-07-02

A read-only Hardware Inventory v0 run on `valera` confirmed:

- Orbbec Astra Pro is visible as `/dev/video0`, `/dev/video1`, and
  `/dev/media0`.
- The user `janus` is in the `video` group.
- `v4l2-ctl --list-devices` reports `Astra Pro HD Camera: Astra Pro`.
- USB inventory shows Orbbec devices `2bc5:0501` and `2bc5:0403`.
- A CH340 USB serial converter is visible as `/dev/ttyUSB0`.
- `/dev/serial/by-id/usb-1a86_USB_Serial-if00-port0` resolves to
  `../../ttyUSB0`.

This confirms the camera path and the SO-ARM 101 motor controller connection
path. The SO-ARM identification is based on operator-confirmed physical kit
provenance: the CH340 adapter is the controller that came with the SO-101 motor
kit. It is not automatic protocol validation.

It does not identify the tracked base. No serial ports were opened. No commands
were sent to devices. No torque or motion was enabled. No arm/base actuation was
attempted.

### Next safe checks

- physically label the CH340 adapter as the SO-ARM 101 motor controller
  connection
- document that `/dev/ttyUSB0` belongs to SO-ARM 101 by operator/kit provenance,
  not by protocol validation
- before opening serial, define a read-only serial probe plan
- serial probe must not send movement commands
- serial probe must not enable torque
- tracked base must remain disabled/off-ground before any future movement test
- SO-ARM 101 must remain in a safe pose and torque-disabled before any future
  motion test

### SO-ARM 101 readiness sequence

Implementation PR phases and hardware bring-up phases use the same numbering
from this point forward.

Phase 0: hardware inventory / operator provenance. Record `/dev/ttyUSB0` and
`/dev/serial/by-id/usb-1a86_USB_Serial-if00-port0` as the SO-ARM 101 motor
controller path based on operator-confirmed kit provenance. This phase is
read-only inventory only: no protocol validation, no serial open, no bytes sent,
no torque enablement, and no movement.

Phase 1: metadata-only SO-ARM readiness.
`scripts/probe_so_arm_readiness.py`
reports the known path, refuses readiness by default, and only performs
filesystem metadata checks after an explicit `--enable-metadata-check` opt-in.
The compatibility flag `--enable-serial-open` is retained, but in Phase 1 it is
metadata-only and does not open serial.

Phase 1 writes local ignored reports under:

- `tmp/so-arm-readiness/latest.json`
- `tmp/so-arm-readiness/latest.md`

The report records timestamp, hostname, user, groups, the known controller path,
resolved target, exists/readable/writable metadata, and the identity basis:
operator-confirmed SO-101 motor kit provenance.

Phase 1 safety flags are all false:

- `serial_opened`
- `serial_commands_sent`
- `torque_enabled`
- `movement_commanded`
- `actuator_calls`

The Phase 1 note is explicit: no serial port is opened and no bytes are sent.

Phase 2: permissions/operator readiness. `scripts/probe_so_arm_readiness.py`
adds an explicit `--enable-permission-check` mode that records Linux
permissions, current user/group membership, and safe operator recommendations.
It remains metadata-only and does not open the serial port.

Phase 2 writes the same ignored local report paths:

- `tmp/so-arm-readiness/latest.json`
- `tmp/so-arm-readiness/latest.md`

Run:

```bash
.venv/bin/python scripts/probe_so_arm_readiness.py --enable-permission-check
```

Useful operator evidence commands:

```bash
id
groups
ls -l /dev/ttyUSB0
readlink -f /dev/ttyUSB0
stat /dev/ttyUSB0
ls -l /dev/ttyUSB* /dev/ttyACM*
```

Allowed Phase 2 checks are limited to:

- check whether the operator is in the Linux group that owns serial access, such
  as `dialout`
- inspect udev/device permissions for the CH340 path and resolved `/dev/ttyUSB0`
  target
- document a safe operator procedure for fixing access, such as group membership
  or udev rules
- re-run Phase 1 metadata reports after permission changes

If `/dev/ttyUSB0` exists but is owned by `root:dialout` with mode `0660`, and
the current user is not in `dialout`, the expected manual operator fix is:

```bash
sudo usermod -aG dialout "$USER"
```

Run that command manually only when appropriate for the host. A logout/login or
reboot is usually required before the new group membership is visible to the
current desktop/session.

If the path does not exist, first check USB connection, power, cable, and serial
device enumeration:

```bash
ls -l /dev/ttyUSB* /dev/ttyACM*
```

Phase 2 completion should prove only that the operator can prepare the machine
for a future protocol/library discovery step. It still must not prove or imply
that the arm is safe to move.

Phase 2 explicitly does not:

- open serial
- read from or write to the serial port
- send bytes
- enable torque
- command movement
- call actuators
- import or call LeRobot hardware-control APIs
- confirm that the serial protocol is valid
- confirm that torque/motor readiness exists
- confirm that the arm is safe to move

Phase 3: adapter contract skeleton. The project now has a project-owned
`ArmAdapter` protocol, `SimArmAdapter`, and `MetadataOnlySOArmAdapter`. Runtime
selection can inject the metadata-only SO-ARM adapter through
`AdapterRuntimeConfig(arm_adapter_kind="metadata_only_so_arm")`.

The metadata-only SO-ARM adapter:

- reports `AdapterType.ARM` in `AdapterMode.PROBE`
- exposes no torque, movement, or read-state capability
- returns `ArmProbeResult` and `ArmState` project-owned types
- records path metadata, read/write access checks, and safety flags
- does not open serial
- does not read from or write to the serial port
- does not send bytes
- does not import or call LeRobot hardware-control APIs
- does not append events or update dashboard artifacts directly

The orchestrator must keep using adapter interfaces only. It must not import
LeRobot, pyserial, serial handles, device paths, or hardware-control APIs
directly.

Phase 4: dry-run arm command envelope. The project now has project-owned
`ArmCommand`, `ArmCommandEnvelope`, and `dry_run_arm_command()` models for
intended arm actions. Supported command intents are `NOOP`, `HOME`,
`MOVE_TO_POSE`, `OPEN_GRIPPER`, `CLOSE_GRIPPER`, and `HOLD_POSITION`.

Phase 4 validation checks command schema, safe target shape, dry-run-only mode,
adapter identity, adapter capabilities, safety preconditions, and low-level
payload exclusions. Targets remain abstract: named poses, named home profiles,
named gripper width/force intents, or duration hints only. They must not include
raw joint angles, servo IDs, torque/current values, serial bytes, or actuator
payloads.

Dry-run results are JSON-serializable and evidence-friendly. They include the
command id, command type, adapter id, adapter mode, dry-run status, blocked
reason, required and unavailable capabilities, safety preconditions,
limitations, and safety flags. The dry-run layer does not append events, write
replay artifacts, update dashboard output, or call enterprise integrations; the
orchestrator may choose to record the returned evidence later.

The safe CLI preview is:

```bash
.venv/bin/python scripts/dry_run_arm_command.py --adapter sim --command noop --reason "verification"
.venv/bin/python scripts/dry_run_arm_command.py --adapter sim --command home --reason "operator preview"
.venv/bin/python scripts/dry_run_arm_command.py --adapter metadata-only-so-arm --command noop --reason "verification"
.venv/bin/python scripts/dry_run_arm_command.py --adapter metadata-only-so-arm --command open-gripper --reason "operator preview"
```

Phase 4 does not execute accepted commands. `SimArmAdapter` may expose simulated
motion capability for existing simulation flows, but Phase 4 still returns
`executable_now: false`. `MetadataOnlySOArmAdapter` exposes no movement,
torque, or read-state capability, so motion-like intents list `can_move` as
unavailable while remaining valid as dry-run intent when the command is safe.

Phase 4 must not open serial, enable torque, command movement, send bytes, call
hardware-control APIs, or import/call LeRobot hardware-control code.

Phase 5: read-only serial identity/state gate. This is the first phase where a
serial port may possibly be opened, and only if the selected protocol/library
supports a safe read-only identity or state query. Phase 5 must not send
movement commands, enable torque, home the arm, or write to the serial port
unless a safe identity protocol plan explicitly justifies the write and receives
separate review.

Phase 6: torque-disabled verification. Verify that the arm remains
torque-disabled before later motion planning. Phase 6 still allows no motion and
no free actuator control.

Phase 7: controlled motion safety plan / first supervised movement. This must be
a separate future PR with an explicit physical safety checklist, emergency stop
or power cut available, tiny supervised movement only, operator present,
evidence logging, and no autonomous motion.

## SO-ARM 101 probe checklist

Probe-only:

- [x] Phase 0 inventory/provenance
- [x] Phase 1 metadata-only readiness
- [x] Phase 2 permissions/operator readiness
- [x] Phase 3 metadata-only SO-ARM adapter skeleton
- [x] Phase 4 dry-run command envelope
- [ ] Phase 5 identify required runtime/library
- [ ] Phase 5 read model/config if possible
- [ ] Phase 5 read joint/state if possible
- [ ] Phase 6 verify torque disabled if applicable
- [ ] Phase 7 first controlled motion plan, not execution unless explicitly
      approved

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
- SO-ARM Phase 1 metadata readiness report generated
- base connection path identified
- no movement performed
- no actuator calls performed
- next PR slices defined

## Follow-up PR slices

- PR Phase 5: read-only SO-ARM serial identity/state gate
- PR Phase 6: torque-disabled verification
- PR Phase 7: controlled motion safety plan / first supervised movement
- tracked base remains separate and probe-only

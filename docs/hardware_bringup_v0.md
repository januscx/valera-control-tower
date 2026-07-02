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

Stage 0: docs/inventory identity. Record `/dev/ttyUSB0` and
`/dev/serial/by-id/usb-1a86_USB_Serial-if00-port0` as the SO-ARM 101 motor
controller path based on operator-confirmed kit provenance.

Stage 1: fail-closed metadata readiness. `scripts/probe_so_arm_readiness.py`
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

Stage 2: permissions-only operator readiness. `scripts/probe_so_arm_readiness.py`
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

Stage 3: adapter contract skeleton. The project now has a project-owned
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

Stage 4: read-only identity/state query. Only add protocol/library reads if the
SO-ARM 101 stack supports identity or state queries without writes, torque
enablement, homing, or movement.

Stage 5: torque-disabled state verification. Verify the arm remains
torque-disabled before any later motion planning.

Stage 6: separate future controlled motion plan. Motion, torque enablement, base
control, and actuator calls remain out of scope for Hardware Bring-up v0 and
must be planned in a separate PR with explicit safety gates.

## SO-ARM 101 probe checklist

Probe-only:

- [x] identify connection/interface by operator-confirmed kit provenance
- [x] verify fail-closed default readiness wrapper
- [x] write metadata-only local readiness reports
- [x] report permissions/operator readiness without opening serial
- [x] define metadata-only SO-ARM adapter skeleton
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
- SO-ARM Phase 1 metadata readiness report generated
- base connection path identified
- no movement performed
- no actuator calls performed
- next PR slices defined

## Follow-up PR slices

- PR A: hardware inventory script/report, read-only
- PR B: SO-ARM protocol/library discovery, no serial read/write until a safe
  read-only plan is defined
- PR C: tracked base probe adapter, no movement
- PR D: hardware safety gate model
- PR E: first controlled motion test plan, docs only, not execution

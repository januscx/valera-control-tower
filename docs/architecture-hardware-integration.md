# Hardware Integration Architecture

## Purpose

Valera Control Tower remains an event-driven orchestration and evidence system.
Hardware runtimes are integrated only through explicit adapters. LeRobot may be
used as an implementation detail of an arm adapter, but it does not define the
project mission model, event schema, or dashboard contract.

This document defines the architecture boundary for integrating the SO-ARM 101,
the tracked Valera platform, and robot cameras without weakening the current
simulation-first safety posture.

## Current Position

The current project already has:

- a task and event model
- deterministic simulation
- fixture-based real vision
- opt-in live camera capture
- a physical demo runner with operator-confirmed manipulation steps
- local evidence artifacts referenced from replay/dashboard output

The current project does not directly control the tracked base or the arm. That
boundary stays intact until explicit hardware safety gates exist.

## Bring-up Status

The camera path has reached live probe status: a local operator can opt in to a
one-frame camera check, and the event/evidence/dashboard pipeline has been
validated with live camera detection and operator-confirmed physical demo
events.

The SO-ARM 101 and tracked Valera base remain unprobed. No real arm motion, real
grasp, real release, base movement, torque enablement, or actuator calls have
been validated. The next step is readiness probing, not control; see
`docs/hardware_bringup_v0.md`.

A read-only inventory run on `valera` confirms the Orbbec Astra Pro camera path
through `/dev/video0`, `/dev/video1`, and `/dev/media0`. The CH340 serial bridge
at `/dev/ttyUSB0` is identified as the SO-ARM 101 motor controller connection by
operator-confirmed kit provenance, not automatic protocol validation. No serial
commands have been sent, no torque or motion has been enabled, and the tracked
base remains unidentified and unprobed.

SO-ARM Readiness Phase 1 adds a fail-closed metadata tool for the known
controller path. The default command exits with code `2`; the explicit
`--enable-metadata-check` path checks filesystem metadata and writes ignored
reports under `tmp/so-arm-readiness/`. The legacy `--enable-serial-open` flag is
kept as a compatibility alias, but it remains metadata-only.

SO-ARM Readiness Phase 2 adds `--enable-permission-check`, which records Linux
device ownership, current user/group membership, read/write access checks, and
safe operator recommendations. Phase 1 and Phase 2 are adapter-adjacent evidence
gathering only. They are not hardware control, not protocol validation, not
torque readiness, and not movement readiness. These probe modes do not open
serial, send bytes, enable torque, command movement, call actuators, run the
live camera, or perform a physical demo.

## Architecture Decision

Use an adapter-first architecture.

The orchestrator owns mission flow and event creation. Adapters expose narrow
hardware or simulation capabilities. Adapters do not write directly to the event
log, dashboard, or enterprise integration layer.

The dashboard is a read-only projection over events and artifacts. It must not
send hardware commands directly. Any future operator action must enter through
an explicit orchestration command path with safety gates and event recording.

```text
Task / Mission Orchestrator
  -> command/request to adapter
  <- adapter result
  -> immutable event appended to TaskEventLog
  -> evidence/artifact refs attached when relevant
```

The event log records facts after they happen. It must not be used as a command
queue.

Hardware probes follow the same boundary. A probe may produce a structured
result for the orchestrator or a local operator report, but it must not append
events directly, update dashboard artifacts directly, or bypass safety gates.
For SO-ARM Readiness Phases 1 and 2, the probe is not an adapter control path at
all: it is a metadata and permissions report over filesystem paths and operator
setup. Phase 3 introduced adapter contracts before any serial/protocol work.
Phase 4 should remain dry-run only; Phase 5 is the first possible serial
identity/state gate.

## Commands, Results, And Events

The system separates three concepts:

- Command/request: what the orchestrator asks an adapter to do.
- Adapter result: what the adapter reports back.
- Event: an immutable fact recorded in the task log.
- Dry-run command envelope: a structured preview of intended arm action before
  any future execution path exists.

Example:

```text
Orchestrator
  -> ArmAdapter.probe()
  <- ProbeResult(status="ok", device="/dev/ttyACM0")
  -> TaskEventLog.append(hardware.probe.completed)
```

This distinction prevents dashboards and replays from showing requested work as
completed work.

## Dry-run Arm Command Envelope

Phase 4 adds a planning layer between mission intent and future adapter
execution. `ArmCommandEnvelope` represents intended arm actions as project-owned
data, and `dry_run_arm_command()` validates that intent against adapter
capabilities and safety rules.

Supported command intents are:

- `NOOP`
- `HOME`
- `MOVE_TO_POSE`
- `OPEN_GRIPPER`
- `CLOSE_GRIPPER`
- `HOLD_POSITION`

These are not hardware commands. They do not map to LeRobot calls, serial
payloads, actuator IDs, torque/current settings, joint angles, or motor units.
Targets are intentionally abstract, such as named poses, named home profiles,
named gripper intents, or non-executable duration hints.

Validation distinguishes schema validity, safety validity, execution
availability, and dry-run acceptability. A safe command intent can be accepted
as a dry-run preview while still returning `executable_now: false`. The result
also records required capabilities, unavailable capabilities, safety
preconditions, limitations, next actions, and safety flags.

The envelope checks adapter capabilities through `ArmAdapter.capabilities()`.
`MetadataOnlySOArmAdapter` continues to expose no movement, torque, or read-state
capability. `SimArmAdapter` may support simulation-specific behavior elsewhere,
but the Phase 4 dry-run envelope still does not execute commands.

Dry-run results are evidence-friendly JSON payloads for future orchestrator
events, replay, dashboard, or enterprise projection. The dry-run layer itself
does not append events, update dashboard artifacts, write replay outputs, or
call enterprise integrations.

The CLI preview is safe and output-only:

```bash
.venv/bin/python scripts/dry_run_arm_command.py --adapter sim --command noop --reason "verification"
.venv/bin/python scripts/dry_run_arm_command.py --adapter metadata-only-so-arm --command open-gripper --reason "operator preview"
```

It has no live execution flag. It must not open serial, send bytes, enable
torque, command movement, call actuator APIs, or import/call LeRobot
hardware-control APIs.

## Serial Open/Close Gate

Phase 5A is the first allowed hardware serial contact. It is intentionally
smaller than an identity/state probe: the operator must pass
`--enable-serial-open-close-check`, the tool opens the SO-ARM serial path with a
timeout, sends no bytes, reads no bytes, and closes the port immediately.

The legacy `--enable-serial-open` flag remains a metadata-only compatibility
alias. It must not open serial.

Phase 5A evidence includes:

- `phase: 5A`
- `mode: serial_open_close_check`
- device path and resolved path
- permission evidence
- `serial_open_attempted`
- `serial_opened`
- `serial_closed`
- serial backend and timeout
- `serial_bytes_written: 0`
- `serial_bytes_read: 0`
- safety flags and limitations

The implementation uses a lazy pyserial backend only inside the explicit Phase
5A gate. If pyserial is unavailable, the result fails closed with
`serial_backend_missing`. The project should not bypass that with raw host file
opens.

Phase 5A does not validate protocol, identity, state, torque, homing, motion
safety, or actuator readiness. It must not import or call LeRobot
hardware-control APIs. It must not append events, update dashboard artifacts, or
write replay outputs directly; the orchestrator can later decide whether to
record returned evidence.

Phase 5B should be planned separately as a read-only identity/state query after
reviewing whether the protocol/library can perform discovery without torque,
homing, movement, or unsafe writes.

## Adapter Failure Semantics

Adapters must fail closed.

Adapter failures should be returned as structured results where possible and
converted by the orchestrator into events such as:

```text
adapter.timeout
adapter.unavailable
hardware.probe.failed
camera.frame.capture_failed
vision.detection.failed
hardware.motion.blocked
```

An adapter failure must not be treated as a successful mission step. If an
adapter result is missing, ambiguous, or unsafe, the orchestrator records a
failure or blocking event and stops, falls back to simulation, or falls back to
operator-confirmed mode.

## Adapter Contracts

Do not create one large `BaseAdapter` that all hardware must inherit from.
Shared identity and health concepts should be small and explicit.

Common adapter identity:

```text
AdapterIdentity
- adapter_id
- adapter_type
- mode: simulation | dry_run | probe | hardware
- capabilities()
- health()
```

Concrete adapter families:

- `ArmAdapter`: arm capability discovery, state reads, and later guarded motion.
- `CameraAdapter`: camera discovery, role assignment, and frame capture.
- `VisionAdapter`: marker/object detection from frames or fixtures.
- `BaseMotionAdapter`: tracked-base motion, deferred until a separate safety
  design exists.

Adapters should return structured result objects. They should not expose
framework-specific objects to the rest of the project.

## Current Adapter Implementation Status

The repository now has a complete simulation adapter path:

- `SimCameraAdapter` is role-based and emits synthetic `sim://` frame artifact
  URIs.
- `SimVisionAdapter` returns configured deterministic detections.
- `SimArmAdapter` reports simulation capabilities and simulated grasp results
  without torque enablement or hardware access.
- `AdapterRuntimeConfig` builds the simulation adapter bundle and fails closed
  for hardware mode.
- `run_adapter_simulated_mission` records adapter results into the event log as
  facts such as `camera.frame.captured`, `vision.object.detected`, and
  `hardware.probe.completed`.

This means the next real-camera or real-arm work should add new adapter
implementations behind the same result models, then extend runtime selection
with explicit safety gates. The domain task model, dashboard replay contract,
and event log should not import camera SDKs, OpenCV live capture objects,
LeRobot objects, serial handles, or device paths.

The SO-ARM adapter contract skeleton is now present:

- `ArmAdapter` protocol and project-owned `ArmCapabilities`, `ArmState`,
  `ArmProbeResult`, and `ArmCommandResult` types.
- `SimArmAdapter` for simulation-only mission flow.
- `MetadataOnlySOArmAdapter` for adapter-shaped SO-ARM path metadata.
- runtime selection through `AdapterRuntimeConfig` without enabling hardware
  mode.

The orchestrator should use only the adapter interface. It should not import
LeRobot, pyserial, serial device paths, or hardware-control libraries directly.
The metadata-only adapter is still not protocol discovery: it does not open
serial, send bytes, enable torque, command movement, or read actuator state.

The Phase 4 dry-run command envelope is also present:

- `ArmCommand`, `ArmCommandEnvelope`, `ArmCommandType`, `ArmCommandValidation`,
  `ArmCommandDryRunResult`, and `ArmCommandSafetyPrecondition` types.
- validation for command id, command type, reason, requester, target shape, and
  dry-run-only mode.
- safety rejection for raw serial bytes, low-level actuator payloads,
  torque/current requests, or movement execution requests.
- evidence-friendly JSON output with all hardware safety flags false.
- no event log, replay, dashboard, enterprise, serial, torque, motion, or
  LeRobot side effects.

## SO-ARM 101 Boundary

The SO-ARM 101 integration should start as probe-only.

Initial allowed behavior:

- detect the controller port
- report configured arm identity through project-owned adapter types
- report metadata-only capabilities
- report filesystem/device permission metadata
- preview intended arm commands through Phase 4 dry-run validation only

Initial disallowed behavior:

- serial open during Phase 1/2/3/4 readiness and dry-run previews
- serial bytes during Phase 1/2/3/4 readiness and dry-run previews
- protocol reads during Phase 1/2/3/4 readiness and dry-run previews
- command execution during Phase 4 dry-run previews
- torque enable
- movement commands
- homing commands
- grasp commands
- automatic recovery motion

LeRobot can be used inside an implementation such as `LeRobotArmAdapter`, but
Valera Control Tower should only see project-owned types:

```text
ArmAdapter
ArmCapabilities
ArmState
ArmCommandResult
TaskEventLog events
```

LeRobot configuration, logs, and internal types should not become the primary
Valera domain model.

## Camera Boundary

Camera selection is separate from camera role. The mission flow depends on roles,
not on physical camera models.

Initial camera roles:

- `front_nav`: forward/base camera for future navigation context.
- `wrist`: camera mounted near the gripper.
- `overhead`: fixed or tower-mounted view of the workspace.
- `operator_view`: optional camera used for demo recording or manual oversight.

Camera events and vision events should stay distinct:

```text
camera.probe.completed
camera.frame.captured
vision.object.detected
vision.object.not_found
```

Images and videos must not be embedded in the event log. The event log stores
artifact references and metadata, such as:

```text
artifact_uri
frame_hash
timestamp
camera_role
camera_id
model_name
confidence
bounding_box
```

The Orbbec Astra can serve as an external/tower depth camera. A small UVC module
can serve as the wrist camera. Anker or Creative webcams can serve as test or
fallback RGB cameras. Those choices are operational details, not mission model
requirements.

## Safety Levels

Hardware access is gated by explicit safety levels:

- `SIM_ONLY`: no hardware access.
- `PROBE_ONLY`: hardware may be detected and queried, but must not move.
- `OPERATOR_CONFIRMED`: the software does not move hardware. It asks the
  operator to perform or confirm a physical step, then records the observed
  outcome.
- `GUARDED_MOTION`: limited motion is allowed with explicit flags, workspace
  profile, and confirmation token.
- `FULL_HARDWARE`: future mode, not part of the current PoC.

CI and replay paths should use simulation or no-op adapters. They must not
require physical devices.

The first SO-ARM 101 serial open/close phase should require flags equivalent to:

```text
--enable-serial-open-close-check
```

This opens and closes the serial path only. It sends no bytes, reads no bytes,
and does not validate protocol or identity.

The later SO-ARM 101 serial identity/state phase should require flags
equivalent to:

```text
--hardware
--probe-only
```

Before that phase, Phase 1 only allows:

```text
scripts/probe_so_arm_readiness.py --enable-metadata-check
```

This records metadata for
`/dev/serial/by-id/usb-1a86_USB_Serial-if00-port0`, which resolves to the CH340
path `/dev/ttyUSB0` on Valera. The identity basis is operator-confirmed SO-101
motor kit provenance. Phase 4 is a dry-run command envelope with no serial
open. Phase 5 is protocol/library discovery before any read-only serial
identity/state probe.

The first motion phase should require flags equivalent to:

```text
--hardware
--allow-motion
--arm-port /dev/...
--workspace-profile tabletop_v1
--confirm-token MOVE_ARM
```

A workspace profile defines the allowed physical envelope for guarded motion:
table bounds, arm mount assumptions, forbidden zones, speed limits, and allowed
motion primitives. Guarded motion cannot run without a workspace profile.

Motion must fail closed when any required gate is missing.

Useful safety event types:

```text
safety.check.started
safety.check.passed
operator.confirmation.required
operator.confirmation.received
hardware.motion.blocked
hardware.motion.executed
```

These events are facts about checks and outcomes. They are not commands.

## Mission Flow

The near-term mission remains hybrid:

```text
task.created
-> task.accepted
-> plan.created
-> route/base step simulated or operator-confirmed
-> object.search_started
-> vision adapter detects object
-> arm step simulated or operator-confirmed
-> delivery step simulated or operator-confirmed
-> task.completed / task.failed
```

Real hardware replaces simulated behavior one adapter at a time:

```text
simulated grasp
-> operator-confirmed grasp
-> probe-only arm status
-> guarded real arm motion
```

The mission event contract should remain stable while adapter implementations
change behind it.

## Proposed PR Slices

1. Architecture document
   - this document
   - adapter boundaries
   - command/result/event separation
   - safety levels
   - phased roadmap

2. Adapter interfaces
   - `robot/adapters/base.py`
   - `robot/adapters/arm.py`
   - `robot/adapters/camera.py`
   - `robot/adapters/vision.py`
   - project-owned capabilities/state/result models
   - no real hardware control

3. Simulation adapters
   - `SimArmAdapter`
   - `SimCameraAdapter`
   - `SimVisionAdapter`
   - current demo code begins using adapters

4. Arm discovery/probe
   - SO-ARM 101 / LeRobot discovery
   - no torque
   - no motion
   - probe/config/state only

5. Camera inventory/probe
   - multiple camera discovery
   - camera roles
   - frame capture artifacts
   - event log references

6. Operator-confirmed demo
   - combined mission replay
   - simulated or operator-confirmed grasp
   - dashboard reads only events

7. Guarded real motion
   - explicit flags
   - workspace bounds
   - confirmation token
   - movement outcome events and evidence

## Non-Goals For The Next Step

- No direct arm motion.
- No tracked-base motion.
- No hardware control from the dashboard.
- No LeRobot types in the Valera mission model.
- No binary image/video data embedded in event JSON.
- No broad `BaseAdapter` abstraction that hides important hardware differences.
- No CI, replay, or dashboard path requiring physical hardware.

## Documentation Split

- `docs/architecture.md`: general task, event, dashboard, replay, and control
  tower architecture.
- `docs/architecture-hardware-integration.md`: hardware adapter boundaries,
  safety model, SO-ARM 101 placement, camera roles, and phased hardware roadmap.
- `docs/hardware-runbook.md`: future operational notes for real ports, commands,
  wiring, troubleshooting, and checklists once there is hardware behavior to run.

## References / Implementation Inputs

- LeRobot SO-101 documentation: https://huggingface.co/docs/lerobot/en/so101
- NVIDIA SO-101 operating notes: https://docs.nvidia.com/learning/physical-ai/sim-to-real-so-101/latest/08-operating-so101.html
- FE-URT-1 manual: https://d2air1d4eqhwg2.cloudfront.net/media/files/5ad7b845-cc46-431d-8c79-46e9c2c5a1d8.pdf

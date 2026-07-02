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

## Architecture Decision

Use an adapter-first architecture.

The orchestrator owns mission flow and event creation. Adapters expose narrow
hardware or simulation capabilities. Adapters do not write directly to the event
log, dashboard, or enterprise integration layer.

```text
Task / Mission Orchestrator
  -> command/request to adapter
  <- adapter result
  -> immutable event appended to TaskEventLog
  -> evidence/artifact refs attached when relevant
```

The event log records facts after they happen. It must not be used as a command
queue.

## Commands, Results, And Events

The system separates three concepts:

- Command/request: what the orchestrator asks an adapter to do.
- Adapter result: what the adapter reports back.
- Event: an immutable fact recorded in the task log.

Example:

```text
Orchestrator
  -> ArmAdapter.probe()
  <- ProbeResult(status="ok", device="/dev/ttyACM0")
  -> TaskEventLog.append(hardware.probe.completed)
```

This distinction prevents dashboards and replays from showing requested work as
completed work.

## Adapter Contracts

Do not create one large `BaseAdapter` that all hardware must inherit from.
Shared identity and health concepts should be small and explicit.

Common adapter identity:

```text
AdapterIdentity
- adapter_id
- adapter_type
- mode: simulation | probe | hardware
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

## SO-ARM 101 Boundary

The SO-ARM 101 integration should start as probe-only.

Initial allowed behavior:

- detect the controller port
- identify the controller/runtime
- report configured arm identity
- report capabilities where safely available
- optionally read servo state without enabling motion

Initial disallowed behavior:

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
- `OPERATOR_CONFIRMED`: operator confirms physical steps; software records facts.
- `GUARDED_MOTION`: limited motion is allowed with explicit flags, workspace
  profile, and confirmation token.
- `FULL_HARDWARE`: future mode, not part of the current PoC.

The first SO-ARM 101 hardware stage should require flags equivalent to:

```text
--hardware
--probe-only
```

The first motion stage should require flags equivalent to:

```text
--hardware
--allow-motion
--arm-port /dev/...
--workspace-profile tabletop_v1
--confirm-token MOVE_ARM
```

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

## Documentation Split

- `docs/architecture.md`: general task, event, dashboard, replay, and control
  tower architecture.
- `docs/architecture-hardware-integration.md`: hardware adapter boundaries,
  safety model, SO-ARM 101 placement, camera roles, and phased hardware roadmap.
- `docs/hardware-runbook.md`: future operational notes for real ports, commands,
  wiring, troubleshooting, and checklists once there is hardware behavior to run.

## References

- LeRobot SO-101 documentation: https://huggingface.co/docs/lerobot/en/so101
- NVIDIA SO-101 operating notes: https://docs.nvidia.com/learning/physical-ai/sim-to-real-so-101/latest/08-operating-so101.html
- FE-URT-1 manual: https://d2air1d4eqhwg2.cloudfront.net/media/files/5ad7b845-cc46-431d-8c79-46e9c2c5a1d8.pdf

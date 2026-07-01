# Office Hours Review: Valera Enterprise Robotics PoC

Date: 2026-07-01
Status: APPROVED
Mode: Builder
Chosen approach: Ideal Stack
Review score: 8/10

## Review Result

The approved direction is an event-driven control tower around one narrow physical workflow. Valera should start from a base, move to a known pickup zone, detect a marked object, pick it with the arm, deliver it to a destination, and return a result report.

The main review correction was to make the architecture concrete enough for planning. The first draft described "event-driven" behavior, but did not name the minimum boundaries, event catalog, and failure handling. The approved version adds those sections so implementation can proceed without guessing.

## Problem Statement

Build a small but understandable PoC with a tracked robot named Valera, a camera, and a robotic arm. The robot should execute one simple physical task: start from a base or dock, travel to a known point, detect a marked object, pick it up, deliver it to another point, and report the result.

The core idea is not "robot drives around the room." The core idea is that a physical robot can be an executor inside a managed digital process. A user creates a task with an object, pickup point, and delivery point. The system turns that task into robot work, records status changes, preserves evidence, and returns a result through a dashboard, chat interface, or enterprise integration.

## What Makes This Cool

The demo becomes compelling when the physical movement and the business process are visibly the same story. A viewer should see a task appear, watch it move through statuses, see Valera perform the action, then inspect a final report with object identity, timestamps, coordinates, photos, logs, and errors if anything failed.

The strongest "whoa" moment is the transition from physical action to enterprise artifact: the cube is in the container, and the system has a clean audit trail proving what happened.

## Constraints

- Keep the first scenario narrow: base to table, object detection, pickup, delivery to container, final report.
- Treat camera recognition as marker-based for MVP: QR code, ArUco marker, color marker, or known shape.
- Do not depend on cloud services for the core demo.
- Do not let the business layer command motors directly.
- Separate simulation, robot adapters, vision adapters, arm adapters, and enterprise workflow.
- Include safety states and explicit failure outcomes from the start.
- Store logs and result records in a local backend before adding any external ERP or service-desk integration.

## Premises

1. The right first problem is not general autonomy. It is one reliable end-to-end task with a business-process wrapper.
2. The event log should be the system's source of truth. UI, reports, and integrations read from the same lifecycle rather than each keeping private state.
3. Hardware control should sit behind adapters. The task engine should not care whether execution is simulated, replayed, or real.
4. The MVP must include failure states. A demo that only handles success does not prove enterprise readiness.
5. The first interface can be simple, but it must show task creation, live status, evidence, and final result.

## Approaches Considered

### Approach A: Thin Demo

Summary: Build the smallest end-to-end system: local backend, simple task lifecycle, minimal dashboard, and one physical or simulated robot run.

Effort: M

Risk: Low

Pros:
- Fastest path to a showable demo.
- Keeps the physical scenario small enough to finish.
- Makes it easy to replace simulated steps with real hardware later.

Cons:
- Architecture may need cleanup before larger integrations.
- Less impressive in architecture discussions if the event model is too shallow.
- Can drift into a one-off demo if discipline slips.

### Approach B: Ideal Stack

Summary: Design the PoC as a small event-driven control tower from day one. The first task is still narrow, but task intake, planning, robot execution, telemetry, evidence, reporting, and integration events are explicit system boundaries.

Effort: L

Risk: Medium

Pros:
- Best long-term trajectory for robotics plus enterprise integration.
- Makes the portfolio story stronger because the architecture explains itself.
- Forces clean separation between business workflow, simulation, and real hardware.

Cons:
- Slower to first visible success than the thin demo.
- More moving parts can hide simple physical-task problems.
- Requires ruthless scope control so "ideal architecture" does not become platform sprawl.

### Approach C: Theater First

Summary: Build the most impressive operator-facing dashboard and replay experience first. Physical execution can be simulated or partially connected until the story is clear.

Effort: M

Risk: Medium

Pros:
- Strongest early presentation for non-technical viewers.
- Helps define exactly what evidence and statuses matter.
- Gives a reusable demo surface even before hardware is reliable.

Cons:
- Can become a beautiful UI wrapped around fake behavior.
- Does not force hardware boundaries early enough.
- May under-test the real task lifecycle and error paths.

## Recommended Approach

Choose Approach B: Ideal Stack, with one hard constraint: only one physical workflow ships first.

The implementation should look like a small control tower, not a full warehouse platform. The first complete path is:

1. User creates a pickup-and-deliver task.
2. Backend stores the task and emits `task.created`.
3. Planner turns it into a small command plan.
4. Executor claims the task and emits `task.accepted`.
5. Robot adapter executes either simulation or real movement.
6. Vision adapter detects the object marker and emits `object.found`.
7. Arm adapter attempts grasp and emits `object.grasped` or an error.
8. Robot delivers the object and emits `delivery.completed`.
9. Backend writes a result report with timestamps, object id, images, coordinates, logs, and final status.
10. UI or chat interface displays the report.

This gives the demo a professional shape without pretending the robot is more capable than it is.

## System Boundaries

### Task API

Owns task creation and validation. It accepts object id, pickup point, destination, and optional operator notes. It does not know motor commands.

### Event Store

Owns the append-only history of the operation. Every UI state, report, and integration message should be derived from events, not from private component memory.

### Planner

Turns a business task into a short command plan: navigate to pickup zone, detect object, align, grasp, navigate to destination, release, report.

### Executor

Claims a task and runs the plan. It emits lifecycle events and delegates physical steps to adapters.

### Robot Base Adapter

Moves Valera between named zones or poses. The first version can be simulated. Real movement comes after explicit safety checks.

### Vision Adapter

Detects the target object using the chosen marker strategy. It returns object id, confidence, image reference, and relative position if available.

### Arm Adapter

Handles grasp and release attempts. It should report success, failure reason, and safety lock state.

### Dashboard or Chat Output

Shows task creation, live timeline, evidence, and final report. It should not invent state that is not present in the event log.

## Event Catalog

The first PoC should support this minimum event set:

- `task.created`: user submitted object, pickup, destination, and notes.
- `task.accepted`: executor claimed the task.
- `plan.created`: planner produced a command plan.
- `route.started`: robot began movement to a named zone.
- `route.arrived`: robot reached the named zone.
- `object.search_started`: vision adapter began detection.
- `object.found`: target marker or shape was detected.
- `object.not_found`: detection timed out or confidence was too low.
- `grasp.started`: arm began pickup attempt.
- `object.grasped`: object was successfully held.
- `grasp.failed`: grasp failed with reason and evidence.
- `delivery.started`: robot began delivery route.
- `object.released`: object was released at destination.
- `delivery.completed`: physical task completed.
- `task.completed`: report finalized and visible to user.
- `task.failed`: operation stopped with failure reason and last safe state.

## Failure Handling

Failures are part of the MVP. The system should make failure understandable rather than pretending it did not happen.

Minimum failures to model:

- object not found
- marker found but confidence too low
- robot cannot reach pickup zone
- alignment failed
- grasp failed
- object dropped or release uncertain
- emergency stop or manual cancel

Each failure should write:

- final task status
- failure code
- human-readable message
- last known zone or pose
- relevant image reference if available
- safe robot state
- next recommended operator action

## UI Sketch Notes

The first dashboard should be operational, not decorative. It should show:

- task intake form
- current mission state
- live event timeline
- robot, vision, and evidence panel
- final result card

The UI should make one thing obvious: a physical action is being tracked like a business process.

## Open Questions

- Which marker type is easiest to make reliable first: QR, ArUco, color, or known shape?
- Is the first robot run fully real, hybrid simulated, or simulation-first with hardware replay later?
- What is the safest gripper task: cube, small box, handled object, or lightweight container?
- Which user output matters first: web dashboard, Telegram/chat, or external-system event?
- What minimum coordinate model is useful: named zones only, 2D room map, or raw robot pose?

## Success Criteria

- A user can create one pickup-and-deliver task with object, pickup point, and destination.
- The system records a full status timeline from task creation to completion or failure.
- The robot execution path can run in simulation without hardware.
- The architecture can swap simulation for real robot adapters without changing the business workflow.
- A final report includes status, duration, object id, evidence image references, coordinates or named zones, logs, and errors.
- A viewer can understand the enterprise story in under two minutes.

## Distribution Plan

The first deliverable is a local developer/demo application, not a public package.

Distribution for MVP:

- GitHub repository with documented local setup.
- Local backend process.
- Local dashboard or chat integration.
- Sample task JSON and recorded replay data.
- Demo script that can run in simulation mode.

CI/CD for MVP:

- Run unit tests for task model, state transitions, and event serialization.
- Run a validation script against a sample pickup-and-deliver task.
- Keep hardware tests manual until explicit safety checks exist.

External distribution through a package manager, container registry, or hosted deployment is deferred until the local PoC is stable.

## Next Steps

1. Define the task lifecycle and event taxonomy before writing robot code.
2. Define the adapter boundary for robot base, camera/vision, and arm.
3. Build a simulation executor that emits the same events a real robot would emit.
4. Build the local result report: final status, timestamps, object id, zones, images, logs, errors.
5. Add a simple dashboard or chat output that reads from the event log.
6. Only then connect one real hardware step at a time.

## Assignment

Before implementation, run one tabletop rehearsal with no code: write a single fake task on paper, then manually list every event that should happen from `task.created` to `delivery.completed` or `task.failed`.

If the event list feels awkward, fix the process before touching robot control.

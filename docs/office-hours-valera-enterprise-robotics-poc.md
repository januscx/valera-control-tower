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

## Benchmark Synthesis

The agent benchmark results support a blended execution style rather than a single-agent doctrine:

- Use the Raw Codex style for speed: small, direct implementation tasks with minimal ceremony.
- Use the Superpowers-style discipline for verification: read back outputs, scan for placeholders, run focused checks, and keep diffs reviewable.
- Use the gstack research-enabled result as the architecture baseline: simulation-first execution, explicit adapter boundaries, task-level control, and enterprise event/status separation.
- Use the GSD Core native workflow idea for documentation hygiene: maintain a canonical doc set and verify it, but do not let workflow artifacts slow down the first demo.

The best near-term choice is therefore not "more planning" or "pure thin demo." It is a show-first control tower built with the gstack research architecture, Raw Codex speed, and Superpowers verification.

## MVP Acceleration Options

### Option 1: Simulator-First Control Tower

Build a polished local simulation of the full pickup-and-deliver lifecycle before touching hardware.

Include:

- task intake
- deterministic simulated execution
- event timeline
- evidence placeholders
- final report
- replayable sample run

Use when the immediate goal is a reliable portfolio walkthrough with no hardware dependency.

Tradeoff: fastest to make stable, but the viewer may still ask what is physically real.

### Option 2: Hybrid Evidence Demo

Build the same control tower, but add one real perception step early: detect a printed fiducial marker from a camera image or webcam feed while navigation and grasp remain simulated.

Include:

- task intake and simulation
- real or recorded camera frame
- ArUco or AprilTag marker detection
- annotated evidence image
- final report that clearly labels `simulation` versus `real_vision`

Use when the demo needs a near-term physical "wow" without risking robot motion.

Tradeoff: slightly more setup than pure simulation, but much stronger proof that the architecture can cross from software into the physical world.

### Option 3: Operator Theater Plus Replay

Build the most impressive dashboard and replay surface first, using recorded or generated event streams.

Include:

- live mission timeline
- robot state panel
- map or named-zone progress
- evidence gallery
- result report
- failure replay

Use when the audience is non-technical or when hardware availability is uncertain.

Tradeoff: visually strong, but less credible unless the data model and simulator are real underneath.

### Option 4: Minimal Physical Act

Make one very constrained real-world action work early: for example, detect a marker and command the arm or base through a guarded, manual step.

Include:

- explicit hardware mode
- safety checklist
- manual operator confirmation
- emergency stop or cancel state
- real evidence capture

Use only if hardware is already available, predictable, and safe to operate.

Tradeoff: highest emotional impact, highest schedule risk.

## Chosen MVP Path

Choose Option 2: Hybrid Evidence Demo.

This is the best short-term balance of speed, credibility, and wow factor. The first public-quality MVP should show the complete enterprise lifecycle in simulation, plus one real perception bridge through marker detection. This proves the control tower is not just a dashboard, while avoiding the risk of rushing tracked-base movement or arm control before safety boundaries exist.

The first demo should explicitly label execution modes:

- `simulation`: route, alignment, grasp, delivery, release
- `real_vision`: marker detection from camera or captured frame
- `future_hardware`: tracked base and arm adapters

The demo story becomes:

1. Create a business task for object `VALERA-CUBE-001`.
2. Show a command plan and correlation id.
3. Run simulated movement from `base` to `pickup_zone`.
4. Detect the real marker on the target object or a printed stand-in.
5. Attach the annotated image to `object.found`.
6. Simulate grasp, delivery, release, and return.
7. Produce a final enterprise-style report with event history, durations, zones, object id, evidence, and a clear simulation/hardware disclosure.

## Must-Ship Wow Features

Do not defer these past the first serious MVP:

- A live event timeline that updates as the mission runs.
- A final audit report with timestamps, object id, zones, duration, status, evidence image, and failure code if applicable.
- A replay mode from saved events so the demo works even without the robot, camera, or perfect lighting.
- At least one modeled failure path, preferably `object.not_found` or `grasp.failed`.
- A visible correlation id that ties task input, events, report, and future enterprise integration together.
- A clear mode badge: `simulation`, `real_vision`, or `hardware`.
- A small architecture diagram showing that enterprise code never commands motors directly.

## External Design Checks

The selected path matches established patterns:

- ROS 2 managed nodes separate component lifecycle from component internals, which supports explicit adapter readiness and safe state transitions.
- Enterprise Integration Patterns distinguish command messages from event messages, which supports task intake as a command and robot lifecycle updates as events.
- OpenCV ArUco and AprilTag-style fiducial markers are practical first perception targets because they provide marker identity and corner/pose information without requiring general object recognition.

For this project, ArUco is the default first marker choice because OpenCV includes built-in marker generation and detection APIs. AprilTag remains a strong alternate if the hardware/perception stack already prefers it.

## Engineering Review Decisions

The engineering review accepted the full boundary model. The first implementation should keep all named boundaries, but make each one small and testable.

Accepted hardening decisions:

- Add a required event envelope contract before implementation.
- Add a fail-closed execution mode gate before any executor can call adapters.
- Add a task state machine with legal transitions and terminal-state rules.
- Add a local evidence store contract for images and annotated outputs.
- Add a concrete implementation layout that follows `AGENTS.md`.
- Add MVP enum lists for zones, modes, event types, and failure codes.
- Choose the local dashboard as the first output surface.
- Add pytest, validation scripts, core invariant tests, and dashboard/replay acceptance tests.

## Event Envelope Contract

Every event should use the same envelope so replay, reports, dashboard state, and later integrations read one source of truth.

Required fields:

- `event_id`
- `task_id`
- `correlation_id`
- `sequence`
- `event_type`
- `occurred_at`
- `source`
- `mode`
- `schema_version`
- `payload`
- `evidence_refs`
- optional `error`

Rules:

- `sequence` must be monotonic per task.
- `event_type` must be one of the MVP event types.
- `mode` must be one of the allowed execution modes.
- Terminal task events must be final: a task cannot complete and fail.
- Evidence should be referenced by id/path metadata, not embedded as image bytes.

## Execution Mode Gate

The executor must validate `execution_mode` before planning or adapter calls.

Allowed MVP modes:

- `simulation`: route, alignment, grasp, delivery, and release are simulated.
- `real_vision`: route, alignment, grasp, delivery, and release are simulated; marker detection may use a real or recorded image.

Reserved future mode:

- `hardware`: tracked base and arm adapters. This must fail closed until a separate safety checklist, manual operator confirmation, and hardware-specific tests exist.

The business workflow must never command motors directly. It can only request a plan and hand execution to an adapter selected by the mode gate.

## Task State Machine

The MVP task lifecycle should be explicit and covered by tests.

```text
task.created
    |
    v
plan.created
    |
    v
task.accepted
    |
    v
route.started -> route.arrived
    |
    v
object.search_started
    |
    +--> object.not_found ----------------+
    |                                      |
    v                                      v
object.found                         task.failed
    |
    v
grasp.started
    |
    +--> grasp.failed --------------------+
    |                                      |
    v                                      v
object.grasped                       task.failed
    |
    v
delivery.started -> route.arrived -> object.released -> delivery.completed
    |
    v
task.completed
```

Terminal-state rules:

- `task.completed` and `task.failed` are mutually exclusive.
- No event may be appended after a terminal task event except diagnostic metadata in a future schema version.
- Manual cancel and emergency stop must end in `task.failed` with a clear failure code and safe state.

## Evidence Store Contract

Evidence should be stored locally and referenced from events.

Recommended layout:

```text
data/
  evidence/
    {task_id}/
      {evidence_id}-raw.png
      {evidence_id}-annotated.png
```

Each evidence reference should include:

- `evidence_id`
- relative path
- media type
- capture mode
- source adapter
- linked `event_id`
- optional checksum

Replay and reports must handle missing evidence with a clear error, not a silent broken image.

## MVP Implementation Layout

Use plain Python first. Keep the code small, boring, and reviewable.

```text
robot/
  __init__.py
  models.py          # task, command plan, result report
  events.py          # event envelope, event types, serialization
  state_machine.py   # legal transitions and terminal-state rules
  adapters.py        # base, vision, and arm adapter protocols
  sim_executor.py    # deterministic simulated mission execution
  evidence.py        # local evidence store helpers

enterprise/
  __init__.py
  schemas.py         # integration-facing task/result/event shapes

scripts/
  run_demo.py
  validate_sample_task.py

data/
  fixtures/
  replay/
  evidence/

tests/
```

Inline ASCII diagrams should be added in:

- `robot/state_machine.py` for legal transitions.
- `robot/sim_executor.py` for the execution pipeline if it grows beyond a few straight-line steps.
- tests that set up non-obvious event histories.

## MVP Enum Lists

Initial zones:

- `base`
- `pickup_zone`
- `delivery_zone`
- `safe_stop`

Execution modes:

- `simulation`
- `real_vision`
- `hardware` reserved, fail-closed for MVP

Failure codes:

- `object_not_found`
- `marker_confidence_low`
- `pickup_unreachable`
- `alignment_failed`
- `grasp_failed`
- `release_uncertain`
- `manual_cancelled`
- `emergency_stop`
- `hardware_mode_not_enabled`
- `invalid_task`

Event types are the entries in the Event Catalog section. Tests should reject unknown values.

## Test Contract

Use pytest for the MVP test harness.

Required commands:

```bash
python -m pytest
python scripts/validate_sample_task.py
```

Blocking unit tests:

- event envelope required fields
- event type validation
- event sequence monotonicity
- legal and illegal task state transitions
- exactly one terminal state
- execution mode gate fail-closed behavior
- zone, mode, event type, and failure code validation
- local evidence reference serialization
- replay/report consistency

Dashboard and replay acceptance checks:

- create a valid pickup-and-deliver task
- reject invalid object id, unknown zone, and unsupported mode
- show correlation id, mode badge, live timeline, evidence, and final report
- replay saved events without camera or hardware
- show clear failure output for `object.not_found` and `grasp.failed`

## Performance Notes

No heavy performance infrastructure is needed for the MVP.

Keep these constraints:

- Replay and report generation should be O(number of task events).
- Evidence files should be loaded lazily by reference.
- The dashboard should derive state from the event log instead of maintaining private state.
- Sample replay data should stay small: one or a few demo missions.

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

### Dashboard Output

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
- Local dashboard integration.
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
5. Add a simple dashboard output that reads from the event log.
6. Only then connect one real hardware step at a time.

## Assignment

Before implementation, run one tabletop rehearsal with no code: write a single fake task on paper, then manually list every event that should happen from `task.created` to `delivery.completed` or `task.failed`.

If the event list feels awkward, fix the process before touching robot control.

## NOT in scope

- Real tracked-base movement: deferred until explicit hardware safety checks exist.
- Real arm control: deferred until manual confirmation, safe workspace assumptions, and hardware tests exist.
- Chat or Telegram output: deferred because the local dashboard is the first output surface.
- External ERP, SAP, service-desk, or cloud integration: deferred until the local event/report model is stable.
- Package-manager, container-registry, or hosted deployment: deferred because the MVP is a local developer/demo application.
- General object recognition: deferred; marker-based detection is the MVP perception boundary.

## What already exists

- `AGENTS.md` already defines repo structure, simulation-first rules, and safety constraints.
- `docs/product-brief.md` already defines the portfolio value proposition and non-goals.
- `docs/roadmap.md` already separates simulation, adapter interfaces, enterprise integration, and hardware demo phases.
- `docs/agent-benchmark-results/` already captures agent workflow lessons that support small direct tasks plus strong verification.
- The office-hours design doc already chooses the hybrid evidence demo and event-driven control tower shape.

## Failure Modes

| Codepath | Production failure | Test coverage required | Error handling required | User output |
|----------|--------------------|------------------------|-------------------------|-------------|
| Task intake | Unknown zone or unsupported mode | pytest validation test | reject before planning | clear validation error |
| Event append | Duplicate terminal event | state-machine invariant test | reject append | clear developer/demo error |
| Replay/report | Missing evidence file | replay acceptance test | missing-evidence placeholder | visible recoverable warning |
| Mode gate | Hardware mode requested during MVP | mode-gate unit test | fail closed | clear safety message |
| Vision adapter | Marker confidence too low | fixture-based vision test | emit `task.failed` | clear failure code and operator action |
| Simulation executor | Illegal event order | state transition test | reject or fail task | clear failure output |
| Dashboard | Timeline diverges from event log | acceptance test | derive from log only | consistent timeline/report |

Critical silent gaps after review: none, assuming the accepted tests are implemented.

## Parallelization Strategy

| Step | Modules touched | Depends on |
|------|-----------------|------------|
| Domain model and enums | `robot/`, `enterprise/` | - |
| Event envelope and state machine | `robot/` | Domain model and enums |
| Sim executor and adapters | `robot/` | Event envelope and state machine |
| Evidence store | `robot/`, `data/` | Event envelope |
| Dashboard | dashboard module, `scripts/` | Event envelope and sim executor |
| Tests and validation script | `tests/`, `scripts/` | All implementation steps |

Lane A: domain model and enums -> event envelope and state machine -> sim executor and adapters.

Lane B: evidence store after event envelope is stable.

Lane C: dashboard after event envelope and sim executor are stable.

Lane D: tests and validation script run alongside each lane, then finish with full replay/report checks.

Execution order: start Lane A first. Once the event envelope stabilizes, Lane B can run in parallel with the executor work. Start Lane C after the sim executor can emit a sample mission. Lane D stays continuous.

Conflict flags: Lane A and Lane B both touch `robot/`; coordinate file ownership or run sequentially if using separate worktrees.

## Implementation Tasks

Synthesized from this review's findings. Each task derives from a specific finding above. Run with Claude Code or Codex; checkbox as you ship.

- [ ] **T1 (P1, human: ~45min / CC: ~8min)** - Event model - Add event envelope contract
  - Surfaced by: Architecture Review - event store source of truth lacked a record contract.
  - Files: `robot/events.py`, `tests/`
  - Verify: `python -m pytest`
- [ ] **T2 (P1, human: ~45min / CC: ~10min)** - Safety gate - Add execution mode gate
  - Surfaced by: Architecture Review - mode labels were not enforced.
  - Files: `robot/models.py`, `robot/sim_executor.py`, `tests/`
  - Verify: `python -m pytest`
- [ ] **T3 (P1, human: ~1h / CC: ~12min)** - Task lifecycle - Add state machine and terminal-state rules
  - Surfaced by: Architecture Review - event catalog lacked legal transitions.
  - Files: `robot/state_machine.py`, `tests/`
  - Verify: `python -m pytest`
- [ ] **T4 (P2, human: ~45min / CC: ~8min)** - Evidence - Add local evidence store contract
  - Surfaced by: Architecture Review - evidence references lacked storage rules.
  - Files: `robot/evidence.py`, `data/`, `tests/`
  - Verify: `python -m pytest`
- [ ] **T5 (P2, human: ~30min / CC: ~6min)** - Project layout - Create concrete MVP module layout
  - Surfaced by: Code Quality Review - named boundaries lacked file ownership.
  - Files: `robot/`, `enterprise/`, `scripts/`, `tests/`
  - Verify: `python scripts/validate_sample_task.py`
- [ ] **T6 (P2, human: ~45min / CC: ~10min)** - Validation - Add MVP enum lists and validation tests
  - Surfaced by: Code Quality Review - accepted values were not explicit.
  - Files: `robot/models.py`, `robot/events.py`, `tests/`
  - Verify: `python -m pytest`
- [ ] **T7 (P2, human: ~1-2d / CC: ~45-90min)** - Dashboard - Build local dashboard as first output surface
  - Surfaced by: Code Quality Review - dashboard/chat scope needed one first surface.
  - Files: dashboard module, `scripts/`, `tests/`
  - Verify: dashboard acceptance checks plus replay validation
- [ ] **T8 (P1, human: ~30min / CC: ~8min)** - Tests - Add pytest harness and validation command
  - Surfaced by: Test Review - repo had no executable test command.
  - Files: `pyproject.toml` or `requirements-dev.txt`, `tests/`, `scripts/validate_sample_task.py`
  - Verify: `python -m pytest && python scripts/validate_sample_task.py`
- [ ] **T9 (P1, human: ~2-3h / CC: ~30-45min)** - Tests - Add core invariant tests
  - Surfaced by: Test Review - state/event/mode invariants were not named as blocking tests.
  - Files: `tests/`
  - Verify: `python -m pytest`
- [ ] **T10 (P2, human: ~2-4h / CC: ~45-90min)** - Tests - Add dashboard and replay acceptance checks
  - Surfaced by: Test Review - user-visible dashboard/replay behavior lacked checks.
  - Files: dashboard tests, `tests/`, `data/replay/`
  - Verify: dashboard acceptance checks and replay validation

## GSTACK REVIEW REPORT

| Review | Trigger | Why | Runs | Status | Findings |
|--------|---------|-----|------|--------|----------|
| CEO Review | `/plan-ceo-review` | Scope & strategy | 0 | - | not run |
| Codex Review | `/codex review` | Independent 2nd opinion | 0 | - | not run |
| Eng Review | `/plan-eng-review` | Architecture & tests (required) | 1 | CLEAR | 10 issues, 0 critical gaps |
| Design Review | `/plan-design-review` | UI/UX gaps | 0 | - | not run |
| DX Review | `/plan-devex-review` | Developer experience gaps | 0 | - | not run |

**VERDICT:** ENG CLEARED - ready to implement the reviewed MVP plan.

NO UNRESOLVED DECISIONS

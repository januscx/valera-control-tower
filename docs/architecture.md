# Architecture

## High-level overview

Valera Control Tower is a local-first robotics and AI integration PoC. It connects business-style task requests, local agent workflows, robot task planning, simulated execution, and future hardware adapters without making enterprise systems depend on robot internals.

The first architecture is intentionally small:

1. An enterprise-facing layer describes tasks, commands, events, and status updates.
2. An agent workflow layer helps humans plan, review, and evolve the project in small changes.
3. A robot domain layer owns robot tasks, robot state, and adapter boundaries.
4. A simulation adapter executes task flows without moving real hardware.
5. A future hardware adapter will connect to the tracked base and arm only after explicit safety design.

## Main components

| Component | Purpose | Current scope |
|---|---|---|
| Enterprise integration | Models external commands, events, and status language | Documentation and schemas first |
| Agents | Supports local coding and operations workflows | Small reviewed tasks only |
| Robot domain | Defines robot tasks, state, and execution concepts | Simulation-ready model |
| Simulation adapter | Exercises task execution without physical movement | First implementation target |
| Hardware adapter | Future bridge to real robot hardware | Not implemented yet |
| Logs and reports | Records task lifecycle and outcomes | Structured local output in a later phase |

## Data and control flow

Initial flow:

1. A user or enterprise-style process creates a robot task request.
2. The task is translated into the internal task model.
3. The robot domain validates the task against known simulated capabilities.
4. The simulation adapter executes the task lifecycle.
5. The robot domain records state changes, task status, and result details.
6. The enterprise layer receives status or event-style updates without direct hardware access.
7. Agents may help inspect results, propose changes, or prepare follow-up tasks.

Enterprise systems should exchange commands, events, and status records. They should not call motor, sensor, arm, or base-control functions directly.

## Simulation-first approach

Simulation is the default execution path until the task model, robot state model, logs, and validation rules are clear. This lets the project demonstrate architecture and behavior without risking physical hardware or inventing unavailable capabilities.

The first simulation should cover:

- task creation
- task validation
- state transitions
- simulated execution steps
- structured result output

Simulation output may describe intended behavior, but it must be labeled as simulated.

## Safety boundary

Real hardware control is outside the current architecture skeleton. Future hardware integration must be added behind an explicit adapter boundary with safety notes, command validation, and clear operator assumptions.

The hardware boundary must preserve these rules:

- Simulation and hardware adapters are separate implementations.
- Enterprise integration never bypasses the robot domain to control hardware.
- Agents do not directly operate real hardware during development tasks.
- Any real movement command requires documented safety constraints before implementation.

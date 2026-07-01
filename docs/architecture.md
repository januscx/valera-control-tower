# Architecture

## System Overview

Valera Control Tower is a local-first control tower for robotics, agents, and enterprise integration experiments.

The first architecture is intentionally small:

1. A user or enterprise-facing process creates a robot task.
2. The task is validated against a simple task model.
3. A robot execution layer runs the task in simulation first.
4. Execution status, logs, and results are reported back as structured output.
5. Enterprise integration receives business-level status and events, not robot hardware internals.

Real hardware control is outside the first implementation. It must be added behind explicit adapter boundaries with safety notes and command validation.

## Main Components

### Task Model

The task model describes what the robot should attempt at a business or operator level. It should avoid direct motor commands or hardware-specific details.

Examples:

- move to an inspection point
- capture state
- point at or pick a target object when supported
- report the result

### Robot Domain

The robot domain owns robot state, command planning, and execution adapters.

It should expose a clear interface that can be backed by:

- a simulation adapter for local development
- a future hardware adapter for real robot control

Simulation and hardware behavior must not be mixed in the same adapter.

### Simulation Adapter

The simulation adapter is the default execution path for the PoC. It should model task lifecycle, state transitions, logs, and result output without moving real hardware.

### Hardware Adapter

The hardware adapter is a future boundary for real robot control. It must include safety checks, explicit operator intent, and clear documentation of what hardware is connected and what commands are allowed.

### Enterprise Integration

The enterprise layer models business-facing commands, events, and statuses. It should translate between enterprise process language and robot tasks without depending on motor control, sensor drivers, or hardware libraries.

### Agent Workflow

Agents assist with planning, implementation, review, and documentation. They should work in small, reviewable changes and should not control real hardware during benchmark or documentation tasks.

## Data and Control Flow

```text
User or enterprise process
  -> enterprise command
  -> robot task model
  -> task validation
  -> simulation adapter
  -> robot state updates
  -> execution logs and result
  -> enterprise status/event output
```

Control flows toward the robot execution layer. Status and events flow back toward the user or enterprise process.

Enterprise integration should see task IDs, task states, timestamps, summaries, and result data. It should not see private robot control internals such as direct actuator commands.

## Simulation-First Approach

The project starts with simulation because it keeps the first PoC safe, repeatable, and easy to review.

Simulation should prove:

- the task model is understandable
- state transitions are clear
- logs and results are useful
- enterprise-facing events can be produced without real hardware

Only after the simulated flow is useful should the project add hardware adapters.

## Safety Boundary

Simulation is allowed to run locally by default.

Real hardware control must remain behind an explicit hardware adapter and should require:

- documented hardware assumptions
- command validation
- safe defaults
- operator awareness
- clear separation from simulation tests

No architecture document or simulation prototype should imply that unsupported hardware capabilities already exist.

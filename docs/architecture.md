# Architecture

## System Overview

Valera Control Tower is a local-first robotics and AI integration PoC. It connects a business-style task request to a robot execution flow while keeping simulation, hardware control, agents, and enterprise integration as separate concerns.

The first architecture is intentionally small:

```text
Enterprise command/status layer
        |
        v
Task model and validation
        |
        v
Robot execution interface
        |
        +--> Simulation adapter
        |
        +--> Hardware adapter (future, safety-gated)
        |
        v
Execution logs and result status
```

## Main Components

- `docs/` documents product intent, architecture, task models, decisions, and roadmap.
- `robot/` owns robot domain concepts, robot state, and adapter boundaries.
- `enterprise/` owns business-facing command, event, and status concepts.
- `agents/` owns agent workflow notes, prompts, and review expectations.
- `experiments/` is reserved for prototypes that should not become core architecture by accident.
- `scripts/` is reserved for repeatable helper commands.

## Data and Control Flow

1. A business-style command describes a requested robot task.
2. The command is translated into the internal task model.
3. The task is validated before execution.
4. The robot execution interface sends the task to an adapter.
5. The simulation adapter is used first and returns state changes, logs, and a result.
6. Enterprise-facing status/events are derived from task state and execution result.

Enterprise systems should not call robot hardware internals directly. They should create commands, read status, and consume events through stable integration contracts.

## Simulation-First Approach

Simulation is the default execution path for the first PoC. It should prove task structure, state transitions, logging, and agent workflows before real movement is attempted.

The simulation layer may model expected robot behavior, but it must not claim capabilities that have not been verified on real hardware. Any simulated behavior should be labeled as simulated in docs, logs, and demos.

## Safety Boundary Between Simulation and Hardware

Real hardware control is out of scope for the architecture skeleton and the first documentation pass.

Before hardware adapters are added, the project should define:

- supported hardware commands
- command validation rules
- emergency stop assumptions
- operator supervision requirements
- safe test environment expectations
- clear logs that distinguish simulation from hardware execution

Hardware adapters should be explicit opt-in components. They should not share code paths that could accidentally turn a simulated task into a real robot command.

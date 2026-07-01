# Architecture

## System overview

Valera Control Tower is a local-first robotics and AI integration PoC. It should make a business-style robot task understandable, simulate its execution, record status, and later provide a safe path toward real hardware.

The first architecture is intentionally small:

```text
User or agent
    |
    v
Enterprise task interface
    |
    v
Task model and validation
    |
    v
Robot execution service
    |
    +--> Simulation adapter
    |
    +--> Hardware adapter (future, safety-gated)
    |
    v
Status, logs, and result report
    |
    v
Enterprise event or status update
```

The control tower should coordinate work at the task level. It should not hide low-level robot safety decisions inside enterprise integration code or agent prompts.

## Main components

### Task model

The task model describes what the robot is being asked to do in plain, structured data. It is the contract between enterprise-facing input, simulation, and future robot execution.

### Robot domain model

The robot domain owns robot state, task state, adapter selection, and execution results. It should expose clear operations such as accepting a task, starting simulated execution, reporting progress, and returning a final result.

### Simulation adapter

The simulation adapter is the first execution target. It should produce deterministic task progress and result output without controlling motors, sensors, arms, or real-world hardware.

### Hardware adapter

The hardware adapter is a future boundary for real Valera platform and LeRobot arm integration. It must stay separate from simulation and must include explicit safety checks before any physical command is sent.

### Enterprise integration layer

The enterprise layer models commands, events, and status updates in business terms. It should not know motor details, arm kinematics, controller topics, or device-specific APIs.

### Agent workflow layer

The agent layer documents how Codex or other local agents help create issues, update docs, implement small changes, and review work. Agents should not directly control robot hardware.

## Data and control flow

1. A user, script, or agent creates a business task.
2. The enterprise layer records the request as a command-like task input.
3. The task model validates required fields, allowed task types, and safe initial state.
4. The robot execution service receives the task.
5. The selected adapter executes the task in simulation first.
6. Execution emits status updates such as accepted, running, succeeded, failed, or canceled.
7. The result report records what was attempted, what happened, and whether the output came from simulation or hardware.
8. The enterprise layer can publish a status or event record without depending on robot internals.

## Simulation-first approach

Simulation is the default path for early development. It allows the project to validate task shape, state transitions, logging, result reporting, and agent workflows before any real hardware is involved.

The simulation path should be:

- local
- repeatable
- explicit about simulated outputs
- safe to run without hardware attached
- useful for tests and portfolio demos

Real hardware work should begin only after the task model, robot state model, and simulated execution flow are clear.

## Safety boundary

Simulation and hardware control are separate execution modes.

```text
Task model
    |
    v
Adapter interface
    |
    +--> Simulation adapter: safe default, no physical effects
    |
    +--> Hardware adapter: future mode, physical effects possible
```

The hardware adapter must not be called implicitly. A future hardware mode should require explicit configuration, clear safety notes, command validation, operator awareness, and a way to stop or refuse unsafe work.

For now, all documentation and future prototypes should assume simulation unless a task explicitly says it is hardware work.

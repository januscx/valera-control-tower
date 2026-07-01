# Architecture Decisions

## Decision 1: Start with documentation and simulation

The project starts with architecture, task model, and simulation documentation before executable robot control.

Why:

- the project is still defining its boundaries
- simulation validates the workflow without physical risk
- documentation makes the PoC easier to explain in interviews and reviews
- real hardware integration needs more safety detail than the first skeleton should invent

## Decision 2: Simulation comes before real hardware

Simulation is the default execution mode until the project has a validated task lifecycle, robot state model, logs, and result reporting.

Why:

- physical robot commands can have real-world consequences
- a simulator can test task states and error paths repeatedly
- the first PoC should be runnable without robot hardware attached
- hardware adapters can be added later behind an explicit boundary

## Decision 3: Separate enterprise integration from robot control internals

Enterprise concepts should describe commands, events, status, correlation IDs, and result reports. Robot control internals should own robot state, adapters, execution, and safety checks.

Why:

- enterprise systems should not depend on motor, sensor, or arm implementation details
- robot internals should not need SAP or other enterprise systems to run locally
- the separation keeps the portfolio story clear: business process in one layer, robot execution in another

## Decision 4: Use task-level control first

The control tower should begin with task-level requests such as inspection or demo manipulation, not direct low-level commands.

Why:

- task-level requests are easier to review and simulate
- low-level control belongs behind robot adapters
- future hardware work can map task steps to safe robot commands when the hardware capabilities are known

## Decision 5: Agents work in small reviewable changes

Codex and other agents should work from small tasks with clear scope, visible diffs, and review expectations.

Why:

- small changes are easier to inspect and correct
- agents can drift when scope is broad or ambiguous
- benchmark runs need clean comparisons
- robotics and integration work both benefit from explicit assumptions

## Decision 6: Do not invent hardware capabilities

Documentation and future code should describe only known or planned capabilities. Unknown real-world behavior should be marked as an assumption or future work.

Why:

- portfolio credibility depends on being clear about what works
- simulation output must not be confused with hardware output
- safety notes are only useful when they are honest about current limits

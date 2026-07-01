# Architecture Decisions

## ADR-001: Start With Simulation

Decision: Valera Control Tower starts with simulated task execution before real hardware control.

Rationale:

- simulation is safer for early development
- task models and state transitions can be tested repeatedly
- documentation and demos can be reviewed without hardware access
- hardware assumptions can be documented later instead of guessed now

Real hardware control will be added only after the simulation path is clear and useful.

## ADR-002: Separate Robot Control From Enterprise Integration

Decision: Enterprise integration concepts live outside robot control internals.

Rationale:

- enterprise processes should work with commands, events, statuses, and results
- robot internals should own task planning, state, and adapter execution
- future hardware changes should not force enterprise schema changes
- business-facing demos should stay understandable to non-robotics reviewers

The enterprise layer may request a task and receive status updates, but it should not issue direct motor or actuator commands.

## ADR-003: Use Adapter Boundaries for Simulation and Hardware

Decision: Simulation and real hardware control should use separate adapters behind a shared robot-domain boundary.

Rationale:

- simulation should be the default local development path
- hardware code requires explicit safety checks and operator awareness
- tests should not accidentally move real equipment
- future hardware work can be reviewed separately from the simulation prototype

## ADR-004: Keep Agent Work Small and Reviewable

Decision: Codex and other agents should work in small, focused changes.

Rationale:

- small diffs are easier to review
- benchmark results are easier to compare
- architecture decisions remain visible
- mistakes are easier to isolate and correct

Agents should document assumptions, avoid secrets, avoid generated junk, and avoid real hardware control unless a task explicitly allows it.

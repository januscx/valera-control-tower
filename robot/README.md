# Robot

## Purpose

The `robot/` package will contain Valera's robot domain model and adapter boundaries. It should own robot tasks, robot state, validation rules, and execution-facing concepts.

This package should not contain enterprise process logic. Enterprise systems may request work and receive status, but robot internals should stay inside the robot layer.

## Simulation adapter vs hardware adapter

The first adapter should be a simulation adapter. It can exercise task validation, state transitions, logs, and result output without controlling physical hardware.

A later hardware adapter may connect to the tracked base and LeRobot-compatible arm. It must be separate from the simulation adapter so tests and demos can run without real movement.

Expected separation:

- Simulation adapter: local, deterministic, safe for development.
- Hardware adapter: future implementation for real devices, with explicit safety constraints.
- Shared robot domain: task and state concepts used by both adapters.

## Safety notes

No real hardware control is implemented yet.

Future hardware work must document:

- supported commands
- unsafe or unsupported commands
- operator assumptions
- validation rules
- emergency stop or shutdown expectations
- how simulation behavior differs from real hardware behavior

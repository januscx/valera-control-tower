# Robot Package

## Purpose

The `robot/` package is reserved for the robot domain model and execution adapters.

It should eventually contain:

- robot task planning
- robot state models
- simulation execution
- hardware adapter interfaces
- command validation

No executable robot control code exists yet.

## Simulation Adapter

The simulation adapter should be the first implementation.

It should:

- run locally without hardware
- model task lifecycle states
- produce structured logs and results
- make assumptions visible
- avoid pretending to perform real movement or manipulation

## Hardware Adapter

The hardware adapter is a future boundary for real robot control.

It should:

- be separate from simulation code
- document supported hardware
- validate commands before execution
- require explicit safety notes
- avoid running during normal simulation tests

## Safety Notes

Real hardware control must not be added casually.

Before hardware control exists, the project should document:

- connected hardware
- supported commands
- unsafe commands or known limitations
- operator responsibilities
- emergency stop or shutdown assumptions

Until then, all examples should be treated as simulation-only.

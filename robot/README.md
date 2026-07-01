# Robot Package

## Purpose

The `robot/` package will hold robot domain models and adapter boundaries for Valera Control Tower.

It should eventually define:

- robot state model
- task execution interface
- simulation adapter
- hardware adapter interfaces
- command validation rules

No executable robot control code exists yet.

## Simulation Adapter vs Hardware Adapter

The simulation adapter should be the default first implementation. It can exercise task state transitions, logs, and result reporting without moving real hardware.

The hardware adapter should come later and should be explicit, safety-gated, and separate from simulation code. A task should never switch from simulation to real hardware by accident.

```text
Task execution interface
        |
        +--> simulation adapter: safe local behavior
        |
        +--> hardware adapter: future real robot control
```

## Safety Notes

- Do not assume real movement, grasping, sensing, or navigation capabilities until verified.
- Keep simulated behavior labeled as simulation.
- Require explicit safety documentation before adding hardware control.
- Keep enterprise commands outside low-level robot control internals.
- Do not connect this package to real robot hardware during documentation or benchmark tasks.

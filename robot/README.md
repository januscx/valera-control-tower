# Robot Package

## Purpose

The `robot/` package will contain the robot domain model for Valera Control Tower. It should own robot-facing concepts such as robot state, task execution, adapters, and execution results.

This package should not contain enterprise workflow logic or agent prompts.

## Simulation adapter

The simulation adapter is the first adapter to build. It should:

- accept validated task data
- simulate task progress locally
- produce predictable status updates
- produce a clear result report
- avoid any physical hardware side effects

Simulation is the default mode for early development and demos.

## Hardware adapter

The hardware adapter is future work. It should be introduced only after the simulation path and safety rules are clear.

The hardware adapter should:

- be separate from the simulation adapter
- require explicit configuration
- validate commands before sending them to hardware
- report failures in a structured way
- document which physical capabilities are real, tested, mocked, or unavailable

## Safety notes

No code in this repository should control real robot hardware until a hardware-specific safety document exists.

Future hardware work should include:

- operator awareness before movement
- safe startup and shutdown behavior
- command validation
- emergency stop or stop-request handling
- clear separation between simulated and physical output

# Enterprise Package

## Purpose

The `enterprise/` package will contain integration-facing models and examples for Valera Control Tower. It should describe how business systems request work and receive status without depending on robot hardware details.

This package should stay focused on integration concepts, not robot control.

## Command, event, and status concepts

Initial concepts:

- command: a request for the control tower to do work, such as creating an inspection task
- event: a fact that something happened, such as `TaskAccepted` or `TaskSucceeded`
- status: the current known state of a task, such as `running` or `failed`
- correlation ID: an identifier that lets external systems connect requests, status updates, logs, and results

These concepts can later become JSON schemas, local files, API payloads, or message examples. They should begin as plain local models and documentation.

## Decoupling from robot hardware

Enterprise integration should not call robot hardware directly.

Preferred boundary:

```text
Enterprise command
    |
    v
Task model
    |
    v
Robot execution service
    |
    v
Simulation or hardware adapter
```

The enterprise layer may know that a task is accepted, running, succeeded, failed, or canceled. It should not know how motors, sensors, controllers, or arm movement are implemented.

This keeps the PoC understandable and allows the robot layer to evolve without rewriting business-facing integration examples.

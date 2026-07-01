# Enterprise

## Purpose

The `enterprise/` package will hold integration-facing concepts for Valera Control Tower. It should describe how business-style systems create tasks, receive events, and observe robot status without depending on robot hardware details.

This layer is for integration models and process examples, not direct robot control.

## Command, event, and status concepts

Initial concepts:

- Command: a request for work, such as creating an inspection task.
- Event: a record that something happened, such as a task being queued, started, completed, or failed.
- Status: the current observable state of a task or robot capability.

These concepts should use stable, plain data structures that can later become JSON examples, API payloads, or message schemas.

## Decoupling from robot hardware

Enterprise integration should stay decoupled from robot hardware by depending on task and status models instead of adapter internals.

Enterprise flows should not:

- call hardware adapters directly
- know motor, arm, or sensor command details
- assume real hardware is available
- treat simulated results as physical execution

The robot layer remains responsible for validating and executing tasks through the selected adapter.

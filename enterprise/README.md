# Enterprise Package

## Purpose

The `enterprise/` package is reserved for business-facing integration models and process examples.

It should help explain how an enterprise system could request robot work and receive status without depending on robot hardware internals.

## Concepts

### Command

A command is a business-level request to create or manage a robot task.

Example:

- create an inspection task for a named location
- cancel a task that has not completed

Commands should not contain direct motor, actuator, or sensor instructions.

### Event

An event records something that happened during the task lifecycle.

Example:

- task created
- task validated
- task started
- task completed
- task failed

Events should be useful for logs, dashboards, and process tracking.

### Status

A status describes the current state of a task or robot-facing workflow.

Example:

- `created`
- `planned`
- `running`
- `succeeded`
- `failed`

Status should be stable enough for enterprise workflows and simple enough for demos.

## Decoupling From Robot Hardware

Enterprise integration should remain decoupled from robot hardware.

The enterprise layer may know:

- task identifiers
- business task types
- lifecycle states
- result summaries
- timestamps
- error summaries

The enterprise layer should not know:

- motor commands
- actuator timings
- sensor driver details
- hardware-specific control loops

This keeps business workflows understandable and allows the robot implementation to change without rewriting enterprise examples.

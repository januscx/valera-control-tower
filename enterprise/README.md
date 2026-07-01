# Enterprise Package

## Purpose

The `enterprise/` package will hold business-facing integration concepts for Valera Control Tower.

It should describe how external workflows request robot work, receive status, and consume result events without depending on robot hardware internals.

## Core Concepts

- Command: a business-level request for robot work.
- Event: a fact emitted by the system, such as task accepted, task started, task failed, or task completed.
- Status: the current readable state of a task or robot execution flow.

These concepts should map to the task model, not directly to motor commands, arm movements, or hardware-specific APIs.

## Decoupling From Robot Hardware

Enterprise integration should stay decoupled from robot control for three reasons:

- business systems need stable contracts even while robot adapters evolve
- simulation should be usable without enterprise systems knowing the difference
- hardware safety rules should live near robot control, not in business process code

Expected flow:

```text
Enterprise command
        |
        v
Internal task model
        |
        v
Robot execution adapter
        |
        v
Enterprise status/event output
```

This package should not contain real hardware control logic.

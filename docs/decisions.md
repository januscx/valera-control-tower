# Architecture Decisions

## ADR-001: Start with documentation and simulation

Decision: The first architecture pass defines documentation, task concepts, and boundaries before executable code.

Reason: The project needs a clear shape before implementation. A concise architecture skeleton makes later Python prototypes easier to review and keeps the repository understandable for portfolio and interview use.

## ADR-002: Simulation comes before real hardware

Decision: Simulation is the first execution target. Real hardware control is deferred.

Reason: The project should validate task flow, state transitions, logging, and integration concepts without moving physical equipment. This reduces risk and avoids inventing capabilities for the tracked base or LeRobot-compatible arm before adapter details are known.

## ADR-003: Keep enterprise integration separate from robot internals

Decision: Enterprise integration models commands, events, and statuses separately from robot control internals.

Reason: Business processes should describe requested outcomes and observe status. They should not know about motors, sensors, arm commands, or adapter-specific details. This keeps the PoC useful for integration discussions while preserving a clean robot domain boundary.

## ADR-004: Agents work in small reviewable changes

Decision: Codex and other agents should operate through narrow tasks with clear review expectations.

Reason: Small changes are easier to inspect, compare, and revert. This matters because the repository is also used to benchmark coding-agent workflows. Agents should document assumptions, avoid secrets, avoid dependency churn, and leave a clean diff.

## ADR-005: Hardware adapters require explicit safety notes

Decision: Any future hardware adapter must include safety documentation before real movement commands are implemented.

Reason: Physical robot control has risks that simulation does not. The project must keep hardware commands behind an adapter boundary with validation, operator assumptions, and clear limits.

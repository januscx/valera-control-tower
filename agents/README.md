# Agents Package

## Purpose

The `agents/` package will document how Codex, local agents, and future operations agents should help build and operate Valera Control Tower.

The first goal is workflow clarity, not autonomous robot control.

## Agent Workflow

Agents should work on small, reviewable tasks:

- read the relevant repository guidance before editing
- state assumptions when hardware behavior is unknown
- keep simulation separate from hardware control
- avoid secrets, tokens, local auth files, and generated junk
- make concise documentation or code changes that a human can review

## Review Expectations

Agent-generated changes should be checked for:

- task fit
- simplicity
- clear architecture boundaries
- safety claims
- Markdown or code readability
- absence of invented hardware capabilities

For benchmark tasks, agents should not commit changes unless explicitly requested.

## Future Agent Roles

Possible future roles:

- planning agent for turning issues into small tasks
- simulation agent for running local task scenarios
- review agent for safety and architecture checks
- operations agent for summarizing logs and task results

These roles should support human review. They should not directly control real robot hardware without explicit future safety design.

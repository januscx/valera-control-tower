# Agents

## Purpose

The `agents/` package will document how Codex and other local agents support Valera Control Tower development and operations.

Agents should help with focused tasks such as documentation updates, simulation prototypes, reviews, test creation, and issue-to-change workflows.

## Working style

Agent work should stay small and reviewable:

- read relevant repository context before editing
- document assumptions when requirements are unclear
- avoid dependency changes unless explicitly requested
- avoid secrets, tokens, credentials, and local auth files
- keep simulation separate from real hardware control
- summarize changed files and validation performed

Agents should not control real robot hardware during benchmark or development tasks.

## Review expectations

Every agent-produced change should be easy for a human to inspect.

Review should check:

- whether the change matches the requested task
- whether simulation and hardware boundaries remain clear
- whether enterprise concepts are decoupled from robot internals
- whether the diff is concise
- whether assumptions and intentionally omitted work are documented

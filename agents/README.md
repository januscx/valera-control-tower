# Agent Workflows

## Purpose

The `agents/` directory is reserved for agent roles, prompts, workflows, and review notes.

Agents may help with:

- planning small implementation tasks
- drafting documentation
- writing simulation code
- reviewing diffs
- keeping project assumptions explicit

## Working Style

Codex or other agents should be used for small, reviewable tasks.

Good agent tasks should:

- have clear inputs and expected outputs
- touch a small number of files
- avoid unrelated refactoring
- avoid secrets and local auth files
- avoid installing dependencies unless explicitly requested
- avoid real hardware control during benchmark tasks

## Review Expectations

Agent output should be reviewed for:

- task fit
- simple architecture
- simulation and hardware separation
- enterprise and robot-domain separation
- readable Markdown or code
- practical assumptions
- absence of generated junk

Agents should summarize what changed, what was assumed, and what was intentionally not implemented.

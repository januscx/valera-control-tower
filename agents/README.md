# Agent Workflows

## Purpose

The `agents/` package will document how Codex and other local AI agents support Valera Control Tower development.

Agents should help with bounded engineering tasks:

- clarify requirements
- update documentation
- implement small changes
- write or run validation scripts
- review diffs
- record assumptions

Agents should not directly control real robot hardware.

## Small task workflow

Use agents for small, reviewable changes:

1. Define the task and expected files.
2. Read the relevant repository context.
3. State assumptions before changing architecture.
4. Make the smallest useful change.
5. Verify the changed files.
6. Report what changed, what was assumed, and what was left out.

This workflow keeps benchmark runs comparable and keeps the project understandable.

## Review expectations

Agent output should be reviewed for:

- task fit
- safety assumptions
- simulation and hardware separation
- enterprise and robot layer separation
- clear Markdown or code
- absence of secrets and local auth files
- unnecessary dependencies or generated junk

For robotics work, review must check whether the change accidentally implies real hardware capability. If a capability is simulated, mocked, or future work, the documentation should say so.

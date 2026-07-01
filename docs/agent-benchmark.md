# Agent Benchmark

## Purpose

This benchmark compares different coding-agent workflows on the same Valera Control Tower tasks.

The goal is not to prove that one tool is fashionable. The goal is to find which workflow produces the best practical result for this project with the least cleanup.

## Baseline reference

Initial benchmark baseline tag: `benchmark-task-a-start`

All benchmark runs should start from this Git tag.

## Candidates

The first comparison includes:

1. Raw Codex baseline
2. Codex + Superpowers
3. Codex + gstack
4. Codex + GSD Core

## Rules

Each candidate must receive the same task prompt.

Each candidate should work from the same baseline commit.

Each candidate should work in its own branch or worktree.

Agents must not commit automatically unless the test explicitly allows it.

Agents must not install dependencies unless the task explicitly requires it.

Agents must not use secrets, tokens, auth files, private keys, or environment files.

Agents must not control real robot hardware during benchmark tasks.

Simulation comes first. Hardware integration comes later.

## Branch naming

Suggested branches:

- benchmark/raw-codex/task-a-architecture
- benchmark/superpowers/task-a-architecture
- benchmark/gstack/task-a-architecture
- benchmark/gsd/task-a-architecture

## Evaluation metrics

Each run should be evaluated from 0 to 10 on:

| Metric | Meaning |
|---|---|
| Task fit | Did it solve exactly what was requested? |
| Simplicity | Did it avoid unnecessary complexity? |
| Architecture clarity | Are simulation, hardware, agents, and enterprise layers clearly separated? |
| Git hygiene | Is the diff clean and reviewable? |
| Safety | Did it avoid risky assumptions and real hardware control? |
| Documentation quality | Is the result readable and useful later? |
| Autonomy | How much manual correction was needed? |
| Final report quality | Did the agent clearly explain what changed? |

## Extra observations

Record these for every run:

- elapsed time
- files changed
- diff size
- commands run
- approvals requested
- tests or validation performed
- manual cleanup needed
- notable strengths
- notable weaknesses

## Tasks

### Task A — Architecture skeleton

Documentation-only task.

Purpose:

- test planning
- test architecture thinking
- test ability to follow project constraints
- test Markdown quality
- avoid dependency noise

Expected files:

- docs/architecture.md
- docs/task-model.md
- docs/decisions.md
- robot/README.md
- enterprise/README.md
- agents/README.md

### Task B — Simulation prototype

Code task.

Purpose:

- test small Python implementation
- test simple CLI design
- test validation
- test whether the agent over-engineers

This task is not ready yet.

### Task C — Review and safety pass

Review task.

Purpose:

- test ability to review another agent's output
- test safety reasoning
- test consistency with AGENTS.md

This task is not ready yet.

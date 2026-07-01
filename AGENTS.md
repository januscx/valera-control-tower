# AGENTS.md

## Project identity

This repository is Valera Control Tower.

It is a portfolio-grade robotics and AI integration project centered around:

- a tracked robot platform called Valera
- a LeRobot-compatible robotic arm
- local AI / coding / operations agents
- enterprise integration patterns
- GitHub-based product development workflow

## Main goal

Build a compact, understandable, expandable PoC that demonstrates how robotics, local AI agents, and enterprise-style integration can work together.

The project should be useful for:

- real experimentation
- portfolio presentation
- job interviews
- architecture discussions
- future hardware integration

## Working rules for agents

- Make small, reviewable changes.
- Prefer boring, explicit, maintainable code.
- Do not invent hardware capabilities.
- Separate simulation from real hardware control.
- Avoid cloud dependencies unless explicitly requested.
- Do not add secrets, tokens, passwords, private keys, or local auth files.
- Do not commit generated junk, logs, caches, or temporary files.
- Keep documentation practical and readable.
- When unsure, document assumptions instead of silently choosing magic.

## Architecture preferences

Prefer this separation:

- `docs/` — product, architecture, roadmap, decisions
- `robot/` — robot domain model and adapters
- `enterprise/` — enterprise integration schemas and process examples
- `agents/` — agent roles, prompts, workflows
- `experiments/` — prototypes and throwaway tests
- `scripts/` — repeatable helper scripts

## Development approach

Start with simulation first.

Real hardware control must come later and must include explicit safety notes.

A good first implementation should include:

- a task model
- a robot state model
- a simulated task execution flow
- structured logs or result output
- tests or at least runnable validation scripts

## Style

- Use clear names.
- Avoid over-engineering.
- Prefer plain Python for first prototypes.
- Add comments only where they explain non-obvious decisions.
- Keep commits focused.

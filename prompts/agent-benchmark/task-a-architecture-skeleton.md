# Task A — Architecture Skeleton

You are working in the Valera Control Tower repository.

Read these files first:

- README.md
- CODEX.md
- AGENTS.md
- docs/product-brief.md
- docs/roadmap.md
- docs/agent-benchmark.md

## Task

Create a first architecture documentation skeleton for the project.

## Requirements

- Do not add external dependencies.
- Do not write executable code yet.
- Do not commit changes.
- Keep the result practical and concise.
- Use plain Markdown.
- Preserve the current repository structure.
- Do not invent real hardware capabilities.
- Keep simulation clearly separated from real hardware control.
- Keep enterprise integration concepts separate from robot control internals.

## Create or update these files

### 1. docs/architecture.md

Include:

- high-level system overview
- main components
- data/control flow
- simulation-first approach
- safety boundary between simulation and hardware

### 2. docs/task-model.md

Include:

- initial robot task model
- task fields
- task states
- a small example JSON task

### 3. docs/decisions.md

Include:

- initial architecture decisions
- why simulation comes before real hardware
- why enterprise integration is modeled separately
- why agents should work in small reviewable changes

### 4. robot/README.md

Include:

- robot package purpose
- simulation adapter vs hardware adapter
- safety notes

### 5. enterprise/README.md

Include:

- enterprise package purpose
- command/event/status concepts
- how enterprise integration should stay decoupled from robot hardware

### 6. agents/README.md

Include:

- agent workflow purpose
- how Codex or other agents should be used in small tasks
- review expectations

## Final response

After editing, summarize:

- files touched
- main decisions made
- assumptions
- anything intentionally not implemented

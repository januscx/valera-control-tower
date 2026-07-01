<!-- generated-by: gsd-doc-writer -->
# Development

## Local Setup

Clone the repository and work from a focused branch:

```bash
git clone https://github.com/januscx/valera-control-tower.git
cd valera-control-tower
git status
```

There is currently no dependency installation step, build step, local service, or environment file to configure.

## Build Commands

No build, development, lint, format, or test commands are defined because the repository does not contain a package manifest, Makefile, or runtime implementation yet.

| Command | Description |
|---|---|
| None detected | No build or development command is currently available. |

## Code Style

Project style is documented in `AGENTS.md` and `CODEX.md`:

- Make small, reviewable changes.
- Prefer boring, explicit, maintainable code.
- Prefer plain Python for first prototypes.
- Add comments only where they explain non-obvious decisions.
- Keep documentation practical and readable.

No formatter or linter configuration is currently present.

## Branch Conventions

No general branch naming convention is documented for all work. The benchmark documentation suggests branch names such as `benchmark/gsd/task-a-architecture` for benchmark runs.

## PR Process

No pull request template or CI workflow is currently present. Until those are added, changes should follow the repository rules:

- Keep changes focused and reviewable.
- Do not add secrets, tokens, private keys, local auth files, generated junk, logs, caches, or temporary files.
- Do not invent hardware capabilities.
- Keep simulation separate from real hardware control.
- Document assumptions when implementation details are not yet known.

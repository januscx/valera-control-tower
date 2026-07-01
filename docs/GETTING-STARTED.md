<!-- generated-by: gsd-doc-writer -->
# Getting Started

## Prerequisites

The current repository is documentation-only. You need:

- Git for cloning and inspecting repository history.
- A text editor or Markdown viewer.

No Python, Node.js, Docker, database, cloud account, robot hardware, or LeRobot setup is required for the current state.

## Installation Steps

1. Clone the repository:

   ```bash
   git clone https://github.com/januscx/valera-control-tower.git
   ```

2. Enter the repository:

   ```bash
   cd valera-control-tower
   ```

3. No install command is required because there is no dependency manifest yet.

## First Run

There is no runnable application, CLI, API server, or simulation entry point yet. The first useful check is to read the project documentation:

```bash
sed -n '1,200p' docs/product-brief.md
sed -n '1,200p' docs/roadmap.md
```

## Common Setup Issues

| Issue | Resolution |
|---|---|
| Looking for an install command | None exists yet; this repository currently contains documentation and benchmark prompts only. |
| Looking for robot hardware setup | Hardware control is intentionally out of scope for the current state. Simulation must come first. |
| Looking for tests or CI | No test framework, validation script, or CI workflow is present yet. See `docs/TESTING.md`. |

## Next Steps

- Read `docs/ARCHITECTURE.md` for the intended system boundaries.
- Read `docs/DEVELOPMENT.md` before adding source code.
- Read `docs/TESTING.md` before introducing tests or validation scripts.
- Read `docs/agent-benchmark.md` before running benchmark tasks.

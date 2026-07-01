<!-- generated-by: gsd-doc-writer -->
# Valera Control Tower

Valera Control Tower is a portfolio-grade robotics and AI integration workspace for designing a simulation-first control tower around the Valera tracked robot concept, a LeRobot-compatible arm concept, local agents, enterprise integration patterns, and GitHub-based product workflow.

## Installation

This repository currently has no package manager, runtime dependency manifest, or install script. Clone the repository and work with the Markdown documentation directly:

```bash
git clone https://github.com/januscx/valera-control-tower.git
cd valera-control-tower
```

No dependency installation is required for the current documentation-only state.

## Quick Start

1. Read the product intent:

   ```bash
   sed -n '1,200p' docs/product-brief.md
   ```

2. Review the roadmap:

   ```bash
   sed -n '1,200p' docs/roadmap.md
   ```

3. Use the generated project docs under `docs/` to understand architecture, configuration, development, and testing expectations.

## Usage Examples

### Understand the PoC Scope

Use [docs/product-brief.md](docs/product-brief.md) to understand the intended PoC: a business-style task becomes a robot command plan, simulated execution state, telemetry or logs, a result report, and an optional enterprise integration event.

### Plan Architecture Work

Use [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) with [docs/roadmap.md](docs/roadmap.md) when deciding where future implementation should live. Simulation must come before real hardware control, and enterprise integration concepts should stay separate from robot control internals.

### Compare Agent Workflows

Use [docs/agent-benchmark.md](docs/agent-benchmark.md) when running benchmark tasks across agent workflows. The benchmark rules prohibit secrets, dependency installation unless requested, and real hardware control.

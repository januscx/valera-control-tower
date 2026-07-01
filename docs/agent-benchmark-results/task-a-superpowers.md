# Task A Result — Codex + Superpowers

## Run identity

- Candidate: Codex + Superpowers
- Branch: `benchmark/superpowers/task-a-architecture`
- Result commit: `4ebed13`
- Baseline tag: `benchmark-task-a-start`
- Task: `prompts/agent-benchmark/task-a-architecture-skeleton.md`
- Superpowers version: `v6.1.0`
- Superpowers commit: `f268f7c953744036f0fa7e9d4b73535c04e57cb8`

## Runtime notes

The successful run used:

`codex exec --dangerously-bypass-approvals-and-sandbox`

This was accepted only because the run happened in a separate benchmark worktree without secrets, dependency installation, network usage, package manager usage, or hardware access.

Superpowers skills were installed through:

`~/.agents/skills/superpowers -> ~/.codex/superpowers/skills`

The prompt explicitly allowed reading Superpowers skills and prohibited other access outside the repository.

## Superpowers behavior observed

The agent read and applied these skills:

- `using-superpowers`
- `writing-plans`
- `verification-before-completion`

It also read:

- `using-superpowers/references/codex-tools.md`
- `brainstorming/SKILL.md`

The agent did not create extra Superpowers plan/spec files, which helped keep the output comparable with the Raw Codex baseline.

## Output summary

Files created:

- `docs/architecture.md`
- `docs/task-model.md`
- `docs/decisions.md`
- `robot/README.md`
- `enterprise/README.md`
- `agents/README.md`

Diff size:

- 6 files changed
- 387 insertions

## Validation

Checks performed during or after the run:

- confirmed all six requested files exist
- read back all created files
- checked line counts
- ran placeholder scan for `TODO`, `TBD`, `implement later`, `fill in details`, and `placeholder`
- checked `git status --short`
- ran `git diff --check`

No problematic content was found.

## Scores

| Metric | Score | Notes |
|---|---:|---|
| Task fit | 9 | Created exactly the requested documentation files. |
| Simplicity | 7 | More verbose than Raw Codex and involved more workflow ceremony. |
| Architecture clarity | 9 | Clearer component decomposition and data/control flow. |
| Git hygiene | 9 | Clean focused diff with the same six requested files. |
| Safety | 9 | Stronger safety framing and explicit placeholder verification. |
| Documentation quality | 8 | Useful and readable, though somewhat more generic in places. |
| Autonomy | 8 | Followed a structured workflow after setup. |
| Final report quality | 9 | Clear summary with verification evidence. |

Average score: 8.5 / 10

## Comparison with Raw Codex

Raw Codex:

- 6 files
- 257 insertions
- simpler output
- less workflow ceremony
- average score: 8.4 / 10

Codex + Superpowers:

- 6 files
- 387 insertions
- stronger process and verification
- more verbose output
- average score: 8.5 / 10

## Notes

Superpowers improved process discipline and verification, but did not dramatically improve the final documentation quality for this small documentation-only task.

The main difference is workflow rigor, not raw output quality.


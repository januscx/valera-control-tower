# Task A Result — Raw Codex

## Run identity

- Candidate: Raw Codex baseline
- Branch: `benchmark/raw-codex/task-a-architecture`
- Result commit: `8df44e1`
- Baseline tag: `benchmark-task-a-start`
- Task: `prompts/agent-benchmark/task-a-architecture-skeleton.md`

## Runtime notes

The first attempts with `read-only` and `workspace-write` sandbox modes failed because the Linux sandbox wrapper could not initialize on Valera.

Observed error:

`bwrap: loopback: Failed RTM_NEWADDR: Operation not permitted`

The successful run used:

`codex exec --dangerously-bypass-approvals-and-sandbox`

This was accepted only because the run happened in a separate benchmark worktree without secrets, dependencies, network usage, package installation, or hardware access.

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
- 257 insertions

## Validation

Manual checks performed:

- `git diff --check`
- line count check
- suspicious content grep for secrets, tokens, package installation, and system commands
- final branch status check

No problematic content was found.

## Scores

| Metric | Score | Notes |
|---|---:|---|
| Task fit | 9 | Created exactly the requested documentation files. |
| Simplicity | 9 | No dependencies, no executable code, no extra tooling. |
| Architecture clarity | 8 | Clear separation of enterprise, robot domain, simulation, hardware, and agents. |
| Git hygiene | 9 | Clean diff with focused files. |
| Safety | 8 | Good hardware boundary, but runtime required full-access fallback. |
| Documentation quality | 8 | Useful first skeleton, slightly generic in places. |
| Autonomy | 7 | Needed sandbox troubleshooting before successful run. |
| Final report quality | 9 | Clear summary of files, decisions, assumptions, and omitted work. |

Average score: 8.4 / 10

## Notes

Raw Codex performed well once the sandbox blocker was bypassed.

The result is a useful baseline for comparing Superpowers, gstack, and GSD Core.

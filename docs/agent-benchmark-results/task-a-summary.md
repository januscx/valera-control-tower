# Task A Benchmark Summary

## Scope

Task A was a documentation-only architecture skeleton task.

Expected output:

- `docs/architecture.md`
- `docs/task-model.md`
- `docs/decisions.md`
- `robot/README.md`
- `enterprise/README.md`
- `agents/README.md`

All runs started from baseline tag `benchmark-task-a-start`.

## Results

| Candidate | Branch | Commit | Time | Diff size | Research | Average | Interpretation |
|---|---|---:|---:|---:|---|---:|---|
| Raw Codex | `benchmark/raw-codex/task-a-architecture` | `8df44e1` | `1m27s` | 257 insertions | No | 8.4 | Fastest and simplest baseline. |
| Codex + Superpowers | `benchmark/superpowers/task-a-architecture` | `4ebed13` | `2m14s` | 387 insertions | No | 8.5 | Strong process and verification discipline. |
| Codex + gstack no-web control | `benchmark/gstack-no-web/task-a-architecture` | `ffbfd91` | `2m13s` | 302 insertions | No | 8.3 | Useful control run, but polluted by Superpowers visibility. |
| Codex + gstack research-enabled | `benchmark/gstack-research/task-a-architecture` | `be5a602` | `3m28s` | 382 insertions | Yes | 8.6 | Best architecture depth and primary gstack result. |

## Main takeaways

Raw Codex is the best speed baseline. It produced a clean architecture skeleton with minimal ceremony.

Superpowers improved process discipline and verification. Its final output was strong, but the improvement over Raw Codex was mostly workflow rigor, not a dramatically better architecture.

gstack no-web control confirmed the official gstack Codex setup works, but it should not be used as the primary gstack result because Superpowers was still visible during that run.

gstack research-enabled produced the strongest architecture skeleton. It made better use of external patterns and framed simulation, hardware, enterprise integration, and agent workflows more carefully. The cost was extra runtime and verbosity.

## Current ranking for Task A

| Rank | Candidate | Reason |
|---:|---|---|
| 1 | Codex + gstack research-enabled | Best architecture depth and product framing. |
| 2 | Codex + Superpowers | Best process discipline among no-research runs. |
| 3 | Raw Codex | Fastest and cleanest baseline. |
| 4 | Codex + gstack no-web control | Useful control, but not a clean primary result. |

## Recommendation

Use Raw Codex for small, obvious documentation or code tasks.

Use Superpowers when verification discipline matters and external research is not needed.

Use gstack research-enabled when architecture judgment, product framing, or unfamiliar design territory matters.

Do not treat gstack no-web as the main gstack result. Keep it as a control run only.

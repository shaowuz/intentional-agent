# Recorded OpenRouter experiments

| Run | Episodes | Model / conditions | Report | Agent transcripts |
|---|---:|---|---|---|
| Terra pilot | 48 | GPT-6.1 Terra; none/public; 0/1 selfish | [Results](pilot-2026-11-07/results/REPORT.md) | [All agents](pilot-2026-11-07/agent_traces/README.md) |
| Luna persona repeat | 24 | GPT-6 Luna; public only; 0/1 selfish; fictional Trump-like selfish persona | [Results](pilot-luna-persona-public-2026-11-07-v2/results/REPORT.md) | [All agents](pilot-luna-persona-public-2026-11-07-v2/agent_traces/README.md) |

Both completed cohorts use 6 players and 20 rounds with matched schedules and
role identities. The Luna repeat changes both model and persona, so comparison
with Terra cannot isolate a personality effect.

The [preliminary Luna launch](pilot-luna-persona-public-2026-11-07/aborted_audit.json)
stopped on a persistent probability-format failure. Its outcomes are excluded.
The completed repeat used the documented, user-authorized extra arithmetic-only
repair once. Each run retains its frozen configuration and runtime.

## Raw request archives

The `.tar.xz` archives contain the exact `seed-*/requests/*.json` files, including
initial prompts, correction messages, accepted responses, and provider/cost
metadata. They omit credentials, account-balance preflight records, environments,
and caches. Extract an archive into its own run directory to restore the original
layout. Human-readable transcripts link to the archive and identify each member.

- [pilot-2026-11-07 — 11,520 request files, 2.99 MB](pilot-2026-11-07/raw-requests.tar.xz)
- [pilot-luna-persona-public-2026-11-07-v2 — 5,760 request files, 1.72 MB](pilot-luna-persona-public-2026-11-07-v2/raw-requests.tar.xz)
- [pilot-luna-persona-public-2026-11-07 — 814 request files, 0.18 MB](pilot-luna-persona-public-2026-11-07/raw-requests.tar.xz)

[Publication manifest and hashes](../publication_manifest.json)

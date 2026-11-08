# Recorded OpenRouter experiments

Browse the [results grouped by selfish-agent count](../results-by-selfish-count/README.md): `selfish-1`, `3 selfish agents results`, and `5 selfish agents results`. The one-selfish-agent result remains unavailable.

## Final five-condition study

| Run | Episodes | Design | Results |
|---|---:|---|---|
| Computer 2: Luna, three selfish players | 60 | 10 players, 10 rounds; all five communication modes; 12 matched seeds | [Report, complete archive, and verification](luna-main-computer-2-selfish-3-2026-11-07/README.md) |
| Computer 3: Luna, five selfish players | 60 | 10 players, 10 rounds; all five communication modes; 12 matched seeds | [Report, complete archive, and analysis](computer-3-luna-selfish-5-2026-11-07/README.md) |
| Computer 3: Sonnet 5.5, five selfish players | 25 | 10 players, 10 rounds; all five modes; seeds 0–4; 1,000-token limit | [Report, complete archive, and Luna comparison](computer-3-sonnet-5.5-1000-seeds5-selfish-5-2026-11-07/README.md) |

The [complete main-study archive](computer-3-luna-selfish-5-2026-11-07/complete-run.tar.xz)
retains all raw requests, frozen runtime, exports, and recovery records. Its
[publication manifest](computer-3-luna-selfish-5-2026-11-07/publication_manifest.json)
records member hashes; the cohort's final export validation passed.

## Earlier pilots

| Run | Episodes | Model / conditions | Report | Agent transcripts |
|---|---:|---|---|---|
| Terra pilot | 48 | GPT-6.1 Terra; none/public; 0/1 selfish | [Results](pilot-2026-11-07/results/REPORT.md) | [All agents](pilot-2026-11-07/agent_traces/README.md) |
| Luna persona repeat | 24 | GPT-6 Luna; public only; 0/1 selfish; fictional Trump-like selfish persona | [Results](pilot-luna-persona-public-2026-11-07-v2/results/REPORT.md) | [All agents](pilot-luna-persona-public-2026-11-07-v2/agent_traces/README.md) |

Both completed pilot cohorts use 6 players and 20 rounds with matched schedules and
role identities. The Luna repeat changes both model and persona, so comparison
with Terra cannot isolate a personality effect.

The [preliminary Luna launch](pilot-luna-persona-public-2026-11-07/aborted_audit.json)
stopped on a persistent probability-format failure. Its outcomes are excluded.
The completed repeat used the documented, user-authorized extra arithmetic-only
repair once. Each run retains its frozen configuration and runtime.

## Earlier pilot request archives

The `.tar.xz` archives contain the exact `seed-*/requests/*.json` files, including
initial prompts, correction messages, accepted responses, and provider/cost
metadata. They omit credentials, account-balance preflight records, environments,
and caches. Extract an archive into its own run directory to restore the original
layout. Human-readable transcripts link to the archive and identify each member.

- [pilot-2026-11-07 — 11,520 request files, 2.99 MB](pilot-2026-11-07/raw-requests.tar.xz)
- [pilot-luna-persona-public-2026-11-07-v2 — 5,760 request files, 1.72 MB](pilot-luna-persona-public-2026-11-07-v2/raw-requests.tar.xz)
- [pilot-luna-persona-public-2026-11-07 — 814 request files, 0.18 MB](pilot-luna-persona-public-2026-11-07/raw-requests.tar.xz)

[Publication manifest and hashes](../publication_manifest.json)

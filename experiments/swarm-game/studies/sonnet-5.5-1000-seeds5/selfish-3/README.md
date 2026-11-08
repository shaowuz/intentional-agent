# Sonnet 5.5: computer 2, three selfish players, 1,000-token limit

All **25/25 episodes completed**, with **5,250 accepted requests**, **1,250 paired encounters**, and **2,500 player actions**. This record is a separate cohort; earlier Luna and Sonnet calibration outputs are not replaced.

Collection source: `e4e1ac41ee41fcea7fcf96e78dead2b853c59014`. Exact model: `anthropic/claude-sonnet-5.5`, routed to Anthropic through OpenRouter with fallbacks disabled. The design uses seeds 0–4, 10 players, 3 selfish players, 10 rounds, neutral personalities, medium reasoning, and rotating-v4. All five conditions retain matched seeded roles and schedules, predetermined leaders, hidden leader roles, and private histories. The content upper limit is 1,000 o200k_base tokens per message/private note; max_completion_tokens remains 4096.

See [saved specification](spec.json), [manifest](matrix_manifest.json), [generated report](report.md), [cell statistics](cells.csv), and [paired contrasts](contrasts.csv). Each condition has five completed seeds. The seed is the sampling unit; these descriptive results do not establish effects for other models or populations.

| Mode | Good-player payoff per encounter | Good cooperation |
|---|---:|---:|
| none | 2.728571 | 99.43% |
| public | 2.848571 | 96.86% |
| opponent | 2.660000 | 95.71% |
| good_leader | 2.634286 | 97.43% |
| selfish_leader | 2.774286 | 99.71% |

## Retry policy and interruptions

The initial run stopped when seed 3 / selfish_leader / round 9 / P10 action exhausted its original two attempts: marginal probabilities totaled 0.93 and then 0.97, below the original validator's lower bound. The user explicitly authorized additional corrections, preserving every original response and the unchanged validator. A separate audited scheduler increases correction_attempts from 1 to 5 (at most six total attempts per request); the frozen runtime files are unchanged. The failed request passed on its third attempt. This retry-policy change is part of the experiment history and must be disclosed in cross-computer comparisons.

The first resume then stopped on OpenRouter HTTP 403 because the API key's total usage limit was exhausted. After the user replaced the key locally, the remaining 318 accepted requests completed using 20 parallel episode workers. The scheduler skipped all previously completed episodes. No accepted response was regenerated or overwritten. Historical failed execution receipts remain historical evidence; [execution.json](execution.json) and the [completion verification](publication-audit/key-refresh-resume-2/completion_verification.json) describe the final state.

There are **5,259 saved response attempts**, including **9 historical invalid responses** and **21 historical transport-error events**. Every planned request ultimately passed the original validation. Provider-reported costs sum to **USD 60.831290**, including corrections; the last resume cost USD 6.419360. This is the cohort's recorded inference cost, not account-wide spending. No saved response lacks a cost value.

All 4,932 responses accepted before the final resume were verified byte-identical afterward. All original attempt prefixes and the five originally completed episode directories were preserved. Final output validation passed and every accepted response was revalidated. [Authorization and policy record](publication-audit/retry-extension-1/authorization.json) and [scheduler diff](publication-audit/retry-extension-1/scheduler.diff) document the exact change.

## Archive and verification

[complete-output.tar.xz](complete-output.tar.xz) contains the output directory plus `publication-audit/`, including original pre-recovery snapshots, all request attempts, checkpoints, manifests, frozen runtime and dependency lock, reports, logs, and recovery scripts/receipts. Expanded review files are byte-identical to their archive members. [archive-manifest.json](archive-manifest.json) records all 10,429 file hashes and explicit exclusions; [SHA256SUMS](SHA256SUMS) covers the archive and manifest.

The archive omits Python caches, lock files, and one account-specific diagnostic containing a private key-management URL. Credentials and environments are never included. Original local files remain intact. The raw request records and logs retain the HTTP 403 evidence. Historical scripts and receipts retain their original local paths; these are provenance, not portable launch commands.

Verify or restore into a new destination (existing destinations are rejected):

```bash
record=experiments/swarm-game/studies/sonnet-5.5-1000-seeds5/selfish-3
python "$record/verify_archive.py"
python "$record/verify_archive.py" --extract /tmp/sonnet-computer-2-restore
```

Using the recorded Python 3.14.0 and locked dependencies, replay reconstructs every request and final checkpoint without hosted calls:

```bash
uv sync --locked --extra dev --no-editable --python 3.14.0
uv run --frozen --no-editable python "$record/verify_archive.py" \
  --replay /tmp/sonnet-computer-2-restore/computer-2-sonnet-5.5-1000-seeds5-selfish-3
```

See [publication verification](publication-validation.json) for archive integrity and full replay results.

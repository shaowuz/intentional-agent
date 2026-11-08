# Sonnet 5.5: five selfish players, seeds 0–4

Completed **25 episodes, 1,250 encounters, and 5,250 accepted requests** using
`anthropic/claude-sonnet-5.5` through OpenRouter, routed to Anthropic with fallbacks
disabled. The run used 10 players, 10 rounds, medium reasoning, neutral personalities,
rotating-v4, and a 1,000-token upper limit for each message and private note with
`o200k_base`. The runner allowed 25 concurrent episodes, one request per episode.

## Results and Luna comparison

Means below use seeds 0–4 for both models, with identical player roles, schedules,
and predetermined leader assignments. Payoff means points per good-player encounter.
Detection is the fraction of good-player/selfish-target pairs assigned at least
80% selfishness probability in the final report.

| Mode | Sonnet payoff | Luna payoff | Sonnet detection | Luna detection |
|---|---:|---:|---:|---:|
| None | 2.548 | 1.412 | 28.8% | 47.2% |
| Public | 2.660 | 1.700 | 43.2% | 48.8% |
| Opponent | 2.080 | 1.376 | 44.0% | 45.6% |
| Good leader | 2.440 | 1.508 | 29.6% | 46.4% |
| Selfish leader | 2.616 | 1.372 | 24.8% | 50.4% |

Sonnet used a 1,000-token limit; the completed Luna comparison used 96 tokens.
These comparisons combine model and message-budget differences. The Luna 960-token
five-mode cohort was paused without completed episodes and contributes no outcomes.
The [published Luna cohort](../../../records/computer-3-luna-selfish-5-2026-11-07/README.md) contains
all 12 seeds; the comparison here selects only seeds 0–4.

Sonnet sent 1,100 messages averaging 56.8 tokens and wrote 1,400 private notes
averaging 88.8 tokens. Six opponent messages were empty. The longest sent message
contained 131 tokens; the longest private note contained 209.

With selfish leaders, all players cooperated in rounds 1–8 in all five seeds, then
all selfish players defected in rounds 9–10. Early cooperation explains the higher
mean good-player payoff relative to good leaders: +10 points in rounds 1–8 and
−1.2 points in rounds 9–10 per episode, for a net +8.8. Selfish leadership improved
payoff in three seeds and tied in two. Public communication had the highest mean.
Five seeds leave the causal contribution of leader wording uncertain.

## Browse and audit

- [Canonical report](report.md), [HTML report](report.html), [aggregate metrics](analysis.json),
  [episodes](episodes.csv), [actions](actions.csv), and [messages](messages.csv).
- [Matched Sonnet/Luna analysis](analysis/sonnet-5.5-vs-luna-selfish5-seeds0-4.json).
- [Communication examples and actions](analysis/sonnet-luna-communication-examples-seed0.json).
- [Message-length measurements](analysis/sonnet-5.5-message-lengths-seeds0-4.json).
- [Leader-pattern decomposition](analysis/sonnet-leader-patterns-seeds0-4.json).
- [Completion receipt](completion.json), [execution/validation](execution.json),
  [publication verification](verification.json), and [hash manifest](publication_manifest.json).

Observer records include true roles, private notes, and beliefs. Experimental agents
received only their permitted histories and messages. Analysis source paths are
relative to the analysis file. Raw request files live in the complete archive under
the same episode paths beneath the named run directory.

## Complete archive

[complete-output.tar.xz](complete-output.tar.xz) preserves the original complete output:
all 5,250 request records and 5,254 received responses including corrections,
checkpoints, manifests, canonical visualization bundle, CSV/JSONL exports, frozen
runtime, dependency lock, and execution receipts. `launch-records/` preserves launch
scripts, logs, configuration, provenance, and the source archive. Locks, bytecode,
virtual environments, and credential files are excluded. Every archived file retains
its original bytes, verified against the publication manifest. The incidental
`visualization 2.json` snapshot is retained; `visualization.json` is canonical.

```bash
mkdir -p restored
tar -xJf complete-output.tar.xz -C restored
PYTHONPATH=restored/computer-3-sonnet-5.5-1000-seeds5-selfish-5/runtime \
  intentional-experiments validate-output restored/computer-3-sonnet-5.5-1000-seeds5-selfish-5
```

Use the restored complete directory for visualization or reproduction. Browseable
files here form a subset of that complete bundle. Original launch paths document
the machine used for execution; adapt paths when restoring elsewhere.

## Provenance and prompt revision

- Source commit: [`e4e1ac41ee41fcea7fcf96e78dead2b853c59014`](https://github.com/shaowuz/intentional-agent/commit/e4e1ac41ee41fcea7fcf96e78dead2b853c59014).
- Run ID: `75e744e1-e283-4751-95eb-c5391477a1d7`.
- Completed November 7, 2026, 22:07 Pacific; elapsed time **7 minutes 35 seconds**.
- Provider-reported cost: **$60.655462**, with cost metadata for all saved responses.
- Runner exit code: **0**; export validation: **valid**.

This completed cohort's original prompt said **"Keep them brief."** Its frozen runtime
and request records preserve that instruction. The shared source prompt published
alongside these results removes that sentence for future runs while retaining the
configured content-token limit. The removal has not been evaluated in this cohort.

The archive filename is standardized here; `publication_manifest.json` preserves its original filename. Archive bytes and raw records are unchanged.

Historical publication hashes remain unchanged in `publication_manifest.json`. Relocated supplemental analysis links are documented in [organization-verification.json](../organization-verification.json); original analysis copies are in `provenance/original-analysis/`. Numerical values and raw archive bytes are unchanged.

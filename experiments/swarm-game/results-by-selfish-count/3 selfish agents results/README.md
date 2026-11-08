# Luna main study: three selfish players (computer 2)

All **60 episodes completed** on November 7, 2026, at 16:52:52 PST. This cohort uses
`openai/gpt-6-luna`, medium reasoning, three selfish players among ten players,
ten rounds, seeds 0–11, and all five communication modes. Roles and encounter
schedules are matched across modes within each seed. The OpenRouter backend,
`rotating-v4` protocol, predetermined hidden-role leaders, private histories, and
96-token message budget are retained.

Collection source: **`e75a825d12fb8b0e77f45f1e486fb02483455ea5`**. The source fix in
this PR was not used to generate these observations; the archived runtime is the
original, unchanged collection runtime. [Configuration](spec.json),
[planned episodes and provenance](matrix_manifest.json), and
[final completion record](completion.json) identify the exact cohort.

## Complete ten-round results

Each mode has 12 episodes. Payoff below is per good player's own encounter
(70 good-player observations per episode), not per paired encounter. Brier scores
use the final reports of good players and exclude their known own role.
Identification is recall at a marginal-probability threshold of 0.8, not overall
classification accuracy.

| Mode | Good payoff / encounter | Good cooperation | Selfish cooperation | Final Brier (lower is better) | Final identification recall |
|---|---:|---:|---:|---:|---:|
| none | 1.9964 | 88.93% | 0.00% | 0.06992 | 43.65% |
| public | 2.2571 | 71.67% | 2.78% | 0.04122 | 60.32% |
| opponent | 1.9690 | 83.81% | 0.00% | 0.08063 | 48.02% |
| good_leader | 2.1071 | 80.95% | 0.00% | 0.06636 | 43.65% |
| selfish_leader | 2.0286 | 89.05% | 0.00% | 0.07805 | 44.05% |

Relative to `none`, `public` increases good payoff by 13.06% and `good_leader` by
5.55%. Both differences are positive in all 12 matched seeds. Public good-player
cooperation is 96.95% against good opponents and 21.63% against selfish opponents;
for `none`, these rates are 92.11% and 82.62% respectively. These are observed
patterns in this cohort, not evidence about other models or selfish-player counts.

| Payoff contrast | Mean paired difference | Exploratory 95% bootstrap interval |
|---|---:|---:|
| public minus none | +0.26071 | [+0.21786, +0.30714] |
| good_leader minus none | +0.11071 | [+0.08095, +0.14286] |
| opponent minus none | -0.02738 | [-0.06667, +0.00952] |
| selfish_leader minus none | +0.03214 | [+0.00119, +0.06667] |

Intervals use 10,000 paired seed-block bootstrap resamples and have no
multiple-comparison adjustment. The statistical unit is the 12 matched seeds,
not individual players, requests, or encounters. Seeds determine roles and
schedules; hosted model responses remain stochastic.

Excluding all five modes for the three seeds with arithmetic recovery (0, 2, 9)
leaves nine matched seeds. The payoff differences remain +0.26825 for `public`
and +0.10635 for `good_leader`; their bootstrap intervals remain positive.
The small `selfish_leader` difference becomes +0.02381 with interval
[-0.00635, +0.06190], so that result is not robust to this sensitivity check.

See [analysis.json](analysis.json), [cells.csv](cells.csv),
[contrasts.csv](contrasts.csv), and the [generated report](report.md).

## Errors, recovery, and preservation

The final record contains **3,000 paired encounters, 6,000 player actions,
12,600 accepted requests, and 12,630 saved response attempts**. Thirty responses
failed validation: 21 marginal-belief sum failures and nine JSON parsing failures.
All requests eventually obtained accepted responses. There are no unresolved
episode errors and no recorded transport-error events. Provider-reported cost is
**USD 10.116417055**, with no saved responses missing a cost value.

Five failures exhausted the original correction allowance and received one
additional, explicitly authorized arithmetic-only model response each:

| Episode | Corrected requests |
|---|---|
| seed 0 / selfish_leader | round 4, 8, and 9 action reports for P10 |
| seed 2 / none | round 10 action report for P8 |
| seed 9 / opponent | round 4 action report for P5 |

Each additional response changed only one specified probability: four by
`0.000002`, and seed 0 / selfish_leader round 9 by `0.000003`. All five
kept the action, strategy, own probability, and other probabilities unchanged,
and passed the original frozen validator. The original attempts, checkpoint,
error, and manifest were archived with SHA-256 before recovery. Actual new model
responses are appended as new attempts; no model output was fabricated or silently
normalized. Recovery receipts and original snapshots are in each episode's
`recovery/rounding-v1/` directory.

This policy is distinct from latest main's optional zero-new-call validation
recovery: that feature was not used for this computer's cohort. The preserved
`parallel_status.json` records historical failures of the first coordinator;
`completion.json` and the final `analysis.json` are the authoritative final state.
Startup receipts and logs are also retained as historical evidence.

## Complete archive and reproducibility

[complete-output.tar.xz](complete-output.tar.xz) contains **every regular file**
from the complete original output directory, including all raw requests/responses,
frozen runtime and prompts, dependency lock, checkpoints, manifests, recovery
snapshots/receipts, logs, table exports, and verification records. Files are not
rewritten. [archive-manifest.json](archive-manifest.json) lists every member's size
and SHA-256; [SHA256SUMS](SHA256SUMS) identifies the archive and manifest. The
expanded files beside this README are a byte-identical review subset, not a second
or replacement cohort. The local `.env` and dependency environment are outside the
original output directory and are not included.

Verify the archive and every expanded review copy with Python 3.11+:

```bash
cohort_record=experiments/swarm-game/records/luna-main-computer-2-selfish-3-2026-11-07
python "$cohort_record/verify_archive.py"
```

Restore to a new directory; the verifier rejects unsafe members and never
overwrites an existing destination:

```bash
python "$cohort_record/verify_archive.py" --extract /tmp/luna-computer-2-restore
```

The original verification scripts are preserved byte-for-byte, including their
machine-local paths. Use the path-aware `verify_archive.py` for a new checkout.
For exact replay, use the recorded Python **3.14.0** and locked dependency versions:

```bash
uv sync --locked --extra dev --no-editable --python 3.14.0
uv run --frozen --no-editable python "$cohort_record/verify_archive.py" \
  --replay /tmp/luna-computer-2-restore/computer-2-luna-selfish-3
```

Replay makes **zero hosted calls**. It imports the extracted frozen runtime,
reconstructs each request's player view, prompts, and schema, validates all accepted
responses, and compares the complete reconstructed checkpoint. It also validates
the canonical visualization bundle against its CSV/JSONL mirrors. All 60 episodes
and 12,600 accepted requests passed this replay before publication; see
[verification](verification/) and the [publication restoration check](publication-validation.json).

## Rounding fix accompanying this record

The collection runtime allowed only `1e-6` total error despite requesting up to six
decimal places per probability. For example, `4 + 6 * 0.166667 = 5.000002` exceeded
its upper bound `5.000001`. Later main already introduced a per-entry rounding
budget. This PR preserves that budget and uses exact decimal sums and inclusive
bounds: binary `math.fsum` can otherwise misclassify an exact boundary by one ULP.
It also reports the actual sum, accepted bounds, and arithmetic correction guidance.

The new regression tests cover the two observed vectors, the demonstrated upper
and lower binary-boundary cases, out-of-budget errors, schema/own-role constraints,
and unchanged legacy behavior. No archived response, checkpoint, prompt, or frozen
runtime is changed by the source fix.

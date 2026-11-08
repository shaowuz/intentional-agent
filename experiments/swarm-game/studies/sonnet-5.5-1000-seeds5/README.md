# Sonnet 5.5: matched five-mode study

Canonical analysis entry for **1, 3, and 5 selfish players among 10 prisoners/players**. All three cohorts are complete: **75 episodes, 3,750 paired encounters, 15,750 accepted requests**. Each count has five modes and seeds 0–4. The exact model is `anthropic/claude-sonnet-5.5`, with medium reasoning, neutral personalities, rotating-v4, 1,000 o200k_base content tokens and a 4096 completion cap. OpenRouter routes only to Anthropic with fallbacks disabled.

## Consistent layout

```text
sonnet-5.5-1000-seeds5/
  README.md
  study.json
  analysis/                  # derived, source-linked combined tables
    episodes.csv             # 75 episode rows
    cells.csv                # 15 count × mode rows
    contrasts.csv            # 30 within-count paired contrasts
    usage.csv                # 15,773 received response attempts
  selfish-1/
  selfish-3/
  selfish-5/
    README.md                # each cohort has these common files
    cohort.json
    spec.json
    matrix_manifest.json
    report.md
    report.html
    episodes.csv
    cells.csv
    contrasts.csv
    usage.csv
    complete-output.tar.xz
    archive-manifest.json
    SHA256SUMS
    verify_archive.py
```

Each cohort keeps its additional original analysis and audit files. Raw requests and frozen runtimes are inside its archive. Old result/record directories contain compatibility links; they are not additional cohorts. Archive contents and original response bytes are preserved. Computer 1's formerly expanded data are now losslessly archived; computer 3's archive was renamed from `complete-run.tar.xz` without changing its bytes. Original computer 3 publication metadata retains the historical archive name.

| Selfish players | Computer | Episodes | Python used for collection | Retry policy | Results |
|---:|---:|---:|---|---|---|
| 1 | 1 | 25/25 | 3.15.2 | Original: one correction | [selfish-1](selfish-1/README.md) |
| 3 | 2 | 25/25 | 3.14.0 | Increased to five corrections after failure | [selfish-3](selfish-3/README.md) |
| 5 | 3 | 25/25 | 3.13.5 | Original: one correction | [selfish-5](selfish-5/README.md) |

All three share identical frozen code/prompt hashes and dependency versions. Computers 2 and 3 explicitly record collection commit `e4e1ac41ee41fcea7fcf96e78dead2b853c59014`. Computer 1's supplied cohort does not record a Git commit; its frozen code/prompt hashes match those cohorts. Do not infer a recorded Git SHA where none was supplied.

## Analysis contract

Start with [analysis/episodes.csv](analysis/episodes.csv); join using `(run_id, episode_id)`. All derived rows include `study_cohort`, `source_csv`, `source_csv_sha256`, and `retry_correction_limit`. Source tables remain unchanged. [study.json](study.json) records compatibility checks, totals, and cohort provenance.

- Compare modes within each selfish count using paired seeds. Seeds, not players, actions or API calls, are the sampling units; there are only five seeds per count.
- Analyze selfish counts separately before comparing them. A shared seed does not imply identical role rosters across different counts. Normalized good-player payoff uses different good-player denominators (9, 7, 5).
- Keep the computer-2 retry-policy extension and collection Python versions visible in sensitivity analyses. Validation was never relaxed; do not describe collection policies as identical.
- `episodes.csv:completed_model_responses` counts received response attempts, including corrections. For accepted requests, filter `usage.csv` to `accepted == True`; each completed episode has 210 accepted requests.
- All three original prompts include "Keep them brief." The later main change removes that sentence only for future experiments. The 1,000-token limit is an upper bound, not a target length.
- Historical Luna cohorts use different model/message-budget settings and are not pooled into these Sonnet tables.

These files prepare analysis inputs; no new statistical effect claims are made by the folder reorganization. Total recorded provider cost across these three cohorts is **USD 183.890946**, including all 15,773 response attempts.

Regenerate the combined inputs from the repository root:

```bash
python scripts/swarm/build_sonnet_study.py
```

## Verification and restoration

Each `verify_archive.py` verifies archive SHA-256, every member hash, and expanded review copies. `--extract` restores into a new directory; existing destinations are rejected. `--replay` reconstructs every request and final checkpoint with zero hosted calls. Replay defaults to exact Python/dependency provenance. To explicitly check data under a different Python version, use `--allow-python-version-difference`; frozen source and dependency hashes/versions must still match, and the verification receipt records both Python versions.

[Reorganization verification](organization-verification.json) records full archive checks, replay, and preservation evidence. All 75 episodes and 15,750 accepted requests were replayed; computer 1 and 3 replay used Python 3.14.0 instead of their collection Python versions. This is a cross-version data reconstruction check, not an exact-environment replay for those two machines.

# Pilot report

## Status

- **Implementation:** complete.
- **Automated tests:** **64/64 pass** (`python3 -m unittest discover -s tests`).
- **Real-LLM pilot:** **DONE** (both conditions, 10 agents, 2 games each).
- **Full experiment:** **NOT launched** (requires explicit approval).

## Real pilot configuration

| Item | Value |
|---|---|
| Provider / model | OpenRouter, `openai/gpt-4o-mini` (OpenAI-compatible) |
| Config | `config/pilot.yaml` |
| Seed | 20240501 |
| Population | 5 priors × 2 agents = 10 agents per condition |
| Games per agent | 2 (fixed horizon = 20 rounds; random = p(continue)=0.95) |
| Output | `results/pilot_openrouter/` |
| Report | `results/pilot_openrouter/report.md` |

The real pilot was launched with:

```bash
python3 -m ipd.cli run --config config/pilot.yaml \
  --provider openai --model openai/gpt-4o-mini \
  --base-url https://openrouter.ai/api/v1 \
  --output-dir results/pilot_openrouter
```

## Execution summary

| Condition | Pair-games | Joint rounds¹ | Agent decisions² | LLM calls | Input tokens | Output tokens |
|---|---:|---:|---:|---:|---:|---:|
| Fixed | 10 | 200 | 400 | 420 | 263,372 | 18,672 |
| Random | 10 | 370 | 740 | 760 | 657,706 | 32,178 |
| **Total** | **20** | **570** | **1,140** | **1,180** | **921,078** | **50,850** |

¹ One joint round contains two simultaneous agent decisions.
² Includes 40 end-of-game belief estimates (20 per condition).

**Estimated cost:** **≈ $0.1687** at `openai/gpt-4o-mini` prices
(input $0.15 / 1M tokens, output $0.60 / 1M tokens), computed from the recorded
token counts with `scripts/report_usage.py` (see
`results/pilot_openrouter/usage_report.txt`). The run-time cost fields recorded
`0.0` because pricing was not configured at launch — this is now handled
explicitly (see “Cost reporting” below).

## Validation

`scripts/validate_run.py` reported **no consistency problems**:

- Fixed: 10 games, exactly 20 rounds each, 400 agent-rounds, 20 belief estimates.
- Random: 10 games, lengths 1–119, 740 agent-rounds, 20 belief estimates.
- All actions and beliefs parsed (`action_parse = ok`, `belief_parse = ok`).
- Every payoff matches the payoff matrix; cumulative payoffs consistent.
- Each agent played exactly 2 games; memory rebuilt consistently.

## Preliminary observations (single run — NOT significant)

- **Cooperation:** fixed horizon 63.5%; random horizon 100% in this sample.
- **Beliefs:** largely stayed near the initial prior (e.g. fixed prior 0.1 → 0.10,
  0.5 → 0.50, 0.9 → 0.875; random groups stayed essentially at their priors).
  This suggests possible **anchoring** to the stated prior and deserves explicit
  follow-up over more games — but 2 games/agent is far too little to conclude.
- **Strategies:** with mostly uninterrupted cooperation, the classifier now
  reports **ties** (e.g. `Tie: Always Cooperate | Tit-for-Tat | Grim Trigger |
  Tit-for-Two-Tats`) instead of arbitrarily picking one. A few agents were
  unambiguously `Always Defect` or `Tie: Always Defect | Grim Trigger`.
- **Random-horizon length:** this sample averaged 37 rounds/game because of a
  heavy tail (one 119-round game). The theoretical expected length is 20; per-game
  payoffs must not be compared across horizons without accounting for game length.
- These are pilot observations from a single seed with n=10; **no statistical
  significance is claimed**.

## Fixes applied after the pilot

1. **Lossless prompt memory.** Previously, older action strings were truncated
   at 80 characters and the in-progress game could be summarised. Now:
   - each completed game contributes its **full** `you_moves`/`opp_moves`
     strings (these reconstruct every payoff), and
   - the current game shows **all** rounds by default.
   `recent_rounds_in_prompt` and `max_completed_game_lines` now use `0 = unlimited`;
   if a window is ever set, the full action sequences are still included, so no
   information is lost.
2. **Strategy ties are reported as indistinguishable.** `classify_strategy`
   returns `Tie: A | B | ...` when several strategies score equally, instead of
   forcing an arbitrary single label. Plots and tables handle these labels.
3. **Cost reporting corrected.** `UsageTracker` now exposes
   `pricing_configured`, emits a `cost_note` when prices are unset (so `0.0` is
   not mistaken for free), logs `n/a (pricing not configured)` during runs, and
   the CLI supports `--price-in/--price-out`. `scripts/report_usage.py`
   recomputes cost from recorded tokens (used to produce the $0.1687 figure).
4. **Tests added** for lossless memory, strategy ties, and cost reporting
   (suite is now 64 tests, all passing).

> **Note:** the real pilot above was run *before* these fixes, so its prompts used
> the older bounded rendering (the recorded raw data are still complete). A short
> re-run with the fixed code is advisable before scaling up, because lossless
> memory can change agent behaviour.

## Security

- The API key was pasted in chat; **rotate it** in the OpenRouter dashboard.
- The temporary credential file `/tmp/ipd_openrouter.env` was removed after the
  run; no key is stored in the repository.

## Next steps before the full experiment

1. Review the observed belief **anchoring** with a medium run (e.g. 5–10 games,
   a few seeds, 10 agents) before spending on 50 agents × 50 games.
2. Set `llm.pricing.*` (or pass `--price-in/--price-out`) so cost is recorded.
3. Decide the number of **independent replications** (whole-run seeds): 3 minimum,
   5 preferred — within-run CIs are not independent because agents interact.
4. Only then launch `config/full.yaml`, with explicit approval.

```bash
# medium check (example)
python3 -m ipd.cli run --config config/pilot.yaml \
  --provider openai --model openai/gpt-4o-mini \
  --base-url https://openrouter.ai/api/v1 \
  --games-per-agent 10 --seed 7 --output-dir results/medium_openai \
  --price-in 0.00015 --price-out 0.0006
```


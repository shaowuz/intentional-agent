# Personality study run, 2026-11-07

**Charts and takeaways for the hackathon: [FINDINGS.md](FINDINGS.md)**

| Cohort | Games | Agents | Model | Cost |
|---|---:|---:|---|---:|
| Main (18 random traits per agent) | 300 (seeds 0-299) | 3,000 | `openai/gpt-6-luna`, medium reasoning | $45.35 |
| Neutral control (no personality) | 24 (seeds 0-23) | 240 | same | $2.98 |
| Pilot | 2 (seeds 0-1) | 20 | same | $0.28 |

10 agents, 10 rounds, public chat, goal "as many points as possible for yourself".
Setup and commands: [docs/personality-study.md](../../../../docs/personality-study.md).
Settings for each cohort: `spec-main.json`, `spec-neutral.json`.

## Files

| File | Contents |
|---|---|
| [analysis/report.md](analysis/report.md) | Summary: overall metrics vs control, strongest trait effects |
| `analysis/trait_effects.csv` | Every trait x metric test: r, p, FDR q, mean at high (8-10) and low (1-3) levels |
| `analysis/agents.csv` | One row per agent: 18 trait levels and 21 behavior metrics |
| `analysis/control_agents.csv` | Same metrics for the neutral control |
| `analysis/transcripts/seed-XXXX.md` | Readable game: each agent's personality, messages, moves, private reasons, final report |
| [analysis/quotes.md](analysis/quotes.md) | Broken promises and messages from the most extreme agents |
| `main-episodes.tar.xz` | Raw game files (every request, response, trust rating, cost). Extract into a run folder to re-analyze |
| `neutral-episodes.tar.xz`, `pilot-episodes.tar.xz` | Same for control and pilot |

Re-analyze from the archives:

```bash
mkdir -p results/personality-main results/personality-neutral
tar -xJf experiments/personality/records/run-2026-11-07/main-episodes.tar.xz -C results/personality-main
tar -xJf experiments/personality/records/run-2026-11-07/neutral-episodes.tar.xz -C results/personality-neutral
PYTHONPATH=backend uv run --frozen --no-editable python -m personality.analyze results/personality-main --control results/personality-neutral
```

## Headline results

- Personality raised cooperation from 3% (control) to 28% and average points from 10.7 to 17.2.
- Honesty-Humility was the strongest trait: high (8-10) vs low (1-3) cooperated 51% vs 15%, broke 13% vs 79%
  of cooperation promises, was betrayed 2.9 vs 0.8 times while cooperating, and earned 13.7 vs 19.4 points.
- Machiavellianism, dark personality and selfishness lowered cooperation and raised revenge, broken promises and points.
- Low Honesty-Humility agents rated their own honesty 1.7/10 (high: 7.0).
- Talkativeness controlled message length (r = 0.94), confirming agents follow assigned traits.
- 43 of 75 traits had at least one effect at FDR q < 0.05 (291 of 1,533 tests). 30 traits, mostly thinking-style
  traits (need for cognition, dogmatism, overconfidence, gullibility, sycophancy...), showed none.

Promise detection is a keyword heuristic; an LLM judge pass is planned.

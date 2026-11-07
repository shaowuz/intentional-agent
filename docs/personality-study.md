# Personality study (Nasser)

Built on the team's rotating Prisoner's Dilemma. **No good/selfish roles**: every agent has the
same goal, *earn as many points as possible for yourself*, and its own random personality.
The question is how personality traits shape cooperation, lying, trust and influence in a swarm.

## Setup

| Setting | Value |
|---|---|
| Agents per game | 10 |
| Rounds | 10 (same seeded rotation as the main study) |
| Communication | Public message before every round (may be empty) |
| Model | `openai/gpt-6-luna`, medium reasoning, pinned to OpenAI on OpenRouter |
| Personality | 2 core traits (Selfishness, Talkativeness) + 2 random traits from each of 8 groups = 18 traits |
| Trait level | 1 (very low) to 10 (very high), drawn per agent from the game seed |
| Control | Same seeds with `--neutral` (no personality) |

Trait catalog and descriptions: [backend/personality/traits.py](../backend/personality/traits.py).
Groups: Big Five and facets, HEXACO, Dark traits, Thinking style, Social influence,
Motivation and risk, Values and morality, Emotional traits.

Each round every agent (1) posts a public message, then (2) chooses C/D against its opponent,
rates its trust in every other player (0-10) and gives a short private reason.
After round 10 each agent privately reports trust, suspected betrayers, a guess of each other
player's personality, a self-rating (honesty, fairness, cooperativeness) and its strategy.

## Run

```bash
# Windows PowerShell: $env:PYTHONPATH="backend"   bash: export PYTHONPATH=backend
uv run --frozen --no-editable python -m personality.run --seeds 0-119 --output results/personality-main          # preview, free
uv run --frozen --no-editable python -m personality.run --seeds 0-1 --output results/p-check --backend scripted --execute  # offline check
uv run --frozen --no-editable python -m personality.run --seeds 0-119 --output results/personality-main --workers 6 --execute
uv run --frozen --no-editable python -m personality.run --seeds 0-23 --output results/personality-neutral --neutral --workers 6 --execute
```

Rerunning the same command resumes: finished games are skipped. `--max-cost` (default $60)
stops launching new games past that spend. Each game is saved to `episodes/seed-XXXX.json`
with personalities, every message, action, trust rating, final report and per-request cost.

## Pilot (2 games, 2026-11-07)

$0.14 per game, about 3 minutes per game, 1 invalid response in 420 (fixed by the retry).
High Selfishness agents defected nearly every round; Talkativeness 10 agents wrote ~260-character
messages versus ~40 for level 1; at least one agent promised cooperation and defected all game.

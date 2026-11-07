# Intentional Agent

One installation, experiment runner, and output contract for **model × communication** experiments in the rotating Prisoner's Dilemma.

## Current experiment

| Setting | Values |
|---|---|
| Model axis | `openai/gpt-6-luna`, `anthropic/claude-haiku-5.5` |
| Reasoning | `medium` for both models |
| Communication axis | `none`, `public`, `leader` |
| Role strata | Zero or one selfish player; analyze separately |
| Population / horizon | 6 players, 20 rounds |
| Replications | 12 matched seeds, 0–11 |
| Personalities | Neutral for everyone |
| Primary outcome | Total cumulative payoff of actual good players |

All players in an episode use the same model. A good player maximizes the collective payoff of actual good players; a selfish player maximizes its own payoff and may cooperate or lie. Players know their own objective and the equal prior over zero/one-selfish episodes. Other objectives and the realized count stay hidden.

Every round matches each player with exactly one opponent. Seeded round-robin cycles give everyone every opponent once per five rounds. Payoffs: CC=(3,3), DC=(5,0), CD=(0,5), DD=(1,1). The runner collects all actions before resolving them and reveals each encounter only to its participants.

### Communication and election

| Condition | Before midpoint | Midpoint, after round 10 | After election |
|---|---|---|---|
| `none` | Private notes | Additional private reflection | Private notes |
| `public` | Everyone broadcasts | Additional private reflection | Everyone broadcasts |
| `leader` | Private notes | Simultaneous secret election | Leader broadcasts; others write private notes |

Election details:

- Each player casts one vote for any player ID, including itself. Plurality wins; a separate seeded random draw breaks ties.
- Everyone receives only the winner's identity. Individual ballots, vote totals, and ballot notes remain private. The observer logs them for analysis.
- The leader's first broadcast follows the election, before round 11 actions. The leader retains the role through the end. Any player, including a selfish player, can win.
- Leadership grants speaking permission. Every player still chooses its own actions; the leader receives only its own encounters and permitted history.
- Notes, public messages, and private midpoint reflections/ballot notes each permit 96 `o200k_base` content tokens. Every player receives one midpoint request, which matches the additional deliberation opportunity across conditions.
- Normal discussion follows rounds 1–19; a final private belief report follows round 20. For other horizons, election follows `floor(rounds/2)`; the horizon must be at least two rounds.
- All messages in a phase commit together. The engine authenticates sender identity and leaves message claims unverified. Nonleaders cannot broadcast through notes or ballots.

Every condition uses identical schedules, roles, identities, and seeds. The runner randomizes execution order within each seed block. Seeds control the design, not hosted-model responses. The shared `medium` setting does not guarantee identical reasoning-token expenditure across providers.

## Setup

Use Python 3.11+ and [uv](https://docs.astral.sh/uv/). From the repository root:

```bash
uv sync --locked --extra dev --no-editable
uv run --frozen --extra dev --no-editable pytest -q
```

Tests use synthetic policies and mocked provider responses. They make no hosted-model requests. The two Docker integration tests require a running Docker daemon; CI requires both to execute.

For hosted experiments, set `OPENROUTER_API_KEY` in the shell or a git-ignored root `.env`. `intentional-experiments` reads `.env`; existing environment values take precedence. Keys never enter experiment logs. Both models use OpenRouter, restricted to their first-party provider: OpenAI for Luna and Anthropic for Haiku. Routing disables fallbacks and requires support for the requested parameters. A catalog check verifies both models before generation.

The model IDs and supported `medium` effort were verified against OpenRouter's public catalog on 2026-11-07. [Haiku listing](https://openrouter.ai/anthropic/claude-haiku-5.5), [reasoning documentation](https://openrouter.ai/docs/guides/best-practices/reasoning-tokens).

## Collaborator workflow

The configuration is [configs/experiment_matrix.json](configs/experiment_matrix.json). All commands below run from the repository root.

**Preview only** — the default makes no requests and creates no run directory:

```bash
uv run --frozen --no-editable intentional-experiments matrix
```

Default size: **2 models × 3 communication conditions × 2 role strata × 12 seeds = 144 episodes**, **8,640 encounters**, **35,424 generation requests before retries**. Each episode uses 246 requests. Input histories grow over time; the 96-token message cap does not bound total API cost.

**Explicitly launch** when ready:

```bash
uv run --frozen --no-editable intentional-experiments matrix \
  --config configs/experiment_matrix.json \
  --output results/luna-haiku-communication --execute
```

Episodes execute sequentially. To launch a smaller cohort, add `--seeds 0` (12 episodes). For a local mechanics check, add `--backend scripted`; outputs clearly identify scripted results. Choose a fresh output directory for each independent cohort.

**Resume** the same cohort with the original configuration and source:

```bash
uv run --frozen --no-editable intentional-experiments matrix \
  --config configs/experiment_matrix.json \
  --output results/luna-haiku-communication --execute --resume
```

The runner saves each accepted response and completed phase. Resumption reuses saved responses, including completed episodes. A configuration or source mismatch stops resumption. Invalid outputs receive one format correction; persistent errors stop the run and leave an explicit partial report. Transport retries are bounded. A response lost before durable recording may require another billed request.

Each matrix saves its runtime source and resolved specification. If application code has changed, use the saved package with the original dependency environment:

```bash
PYTHONPATH=results/luna-haiku-communication/runtime \
  .venv/bin/python -m swarm_game.cli matrix \
  --config results/luna-haiku-communication/spec.json \
  --output results/luna-haiku-communication --execute --resume
```

**Rebuild analysis** without model calls:

```bash
uv run --frozen --no-editable intentional-experiments analyze \
  results/luna-haiku-communication
```

## Unified outputs

The visualization team's stable entry point is **`visualization.json`**, with contract version **`intentional-agent.visualization/1`**. It uses fixed typed tables, explicit nulls, stable run/episode IDs, and an atomic snapshot. The [visualization handoff](docs/visualization/README.md) includes a JSON Schema, generated TypeScript types, synthetic complete/incomplete fixtures, and parsing rules.

Validate exports without model calls:

```bash
uv run --frozen --no-editable intentional-experiments validate-output results/luna-haiku-communication
```

Every matrix writes the same files, regardless of model or communication condition:

| File | Contents |
|---|---|
| `visualization.json`, `visualization.schema.json` | Validated visualization bundle and machine-readable contract |
| `output_identity.json` | Stable cohort identity; keep this with archived outputs |
| `matrix_manifest.json`, `spec.json` | Full planned cells, randomized order, configuration, source provenance |
| `analysis.json`, `report.md`, `report.html` | Combined analysis and portable reports |
| `episodes.csv`, `cells.csv` | Episode metrics and model/communication/role means |
| `contrasts.csv` | Paired communication and model contrasts, bootstrap intervals |
| `actions.csv` | One row per player-round: opponent, action, payoff, role |
| `beliefs.csv` | Private identity probabilities and brief recorded strategy summaries |
| `messages.csv` | Public messages and private notes, with explicit visibility |
| `elections.csv` | Observer-only ballots, winner, true role, tie status |
| `usage.csv`, `status.csv` | Response attempts, cost, provider metadata, and missing/incomplete cells |
| `events.csv`, `timeline.jsonl` | Fixed event envelopes with typed payloads and stable sequence IDs |
| `episodes/*/` | Checkpoints, exact permitted prompts, responses, and episode reports |
| `runtime/` | Saved runner, prompts, and dependency provenance |

The visualization contract is `intentional-agent.visualization/1`; the matrix manifest uses `intentional-experiments/1`, and the experimental protocol is `rotating-v2`. Report normalized good return as total good payoff divided by `rounds × good_player_count`. Other metrics include good–good/good–selfish contributions, cooperation, identity Brier scores, identification at 0.8, false accusations, pre/post-midpoint return, and election of a selfish leader.

Contrasts match complete seed blocks and retain separate zero/one-selfish strata. They compare communication within each model and models within each communication condition. Bootstrap intervals resample seed blocks; they use 10,000 resamples and remain null with fewer than two pairs. Missing cells remain explicit, and cost summaries include failed/incomplete episodes. Collective return and identification measure distinct outcomes; a cooperative selfish player can improve return without becoming identifiable.

Observer exports include true roles and private reports. The engine builds each agent's prompt from an explicit information allowlist; agents receive no observer exports or tools.

## Code organization and compatibility

```text
backend/swarm_game/        canonical matrix runner, protocol, provider, and analysis
backend/intentional_agent/ existing interactive dashboard and API
backend/ipd/               historical fixed/random-horizon protocol
configs/experiment_matrix.json
config/                    historical IPD configurations
scripts/swarm/             historical pilot reporting and recovery tools
tests/                     one shared test suite, including tests/swarm/
experiments/swarm-game/records/  immutable Terra/Luna pilot records
pyproject.toml, uv.lock     single installation and dependency lock
```

`swarm-game` remains an alias for `intentional-experiments`. Historical `compare`/`pilot` commands retain `rotating-v1` (240 requests per default episode); they do not include the new midpoint control. Current single-episode `run` defaults to `rotating-v2`. Historical runs retain their recorded prompts, frozen runtimes, and output formats; the new matrix never pools them into its estimates.

The existing dashboard and IPD entry points remain available for their original protocols; the matrix CLI above is the canonical path for this study. All packages now share the root install and payoff definition. See [legacy workflows](docs/legacy-workflows.md) for the original interfaces and [recorded pilots](experiments/swarm-game/records/README.md) for prior results. Do not treat the historical Trump-like persona pilot as a neutral Haiku/Luna matrix cell.

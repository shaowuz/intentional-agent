# Intentional Agent — collaborator guide

Compare **Luna and Haiku** across **no communication, public communication, and an elected leader** in a rotating Prisoner's Dilemma. This repository provides one runner, reproducible configurations, and a versioned output contract for the visualization team.

## Start here

| Your task | Where to start | What you need |
|---|---|---|
| Run experiments | [Setup and preview](#setup-and-preview), then [launch](#run-experiments) | Repository access, Python 3.11+, uv; an OpenRouter key for hosted runs |
| Build visualizations | [Visualization quickstart](#visualization-quickstart) | The JSON fixture or a run's `visualization.json`; an API key is unnecessary |
| Analyze or review results | [Analyze and share results](#analyze-and-share-results) | A saved run directory and the Python environment |
| Change code or prompts | [Contribute changes](#contribute-changes) | The development environment and relevant tests |

<a id="collaborator-workflow"></a>

## Setup and preview

Use Git, Python 3.11+, and [uv](https://docs.astral.sh/uv/). Clone with a GitHub account that has access to the repository:

```bash
git clone https://github.com/shaowuz/intentional-agent.git
cd intentional-agent
uv sync --locked --extra dev --no-editable

# Inspect the planned experiment; this makes no model calls.
uv run --frozen --no-editable intentional-experiments matrix
```

Run every command below from the repository root. The preview creates no run directory and needs no API key. Node.js is needed only for dashboard development; the matrix CLI uses Python.

The default [experiment configuration](configs/experiment_matrix.json) specifies:

| Models | Communication modes | Selfish-player groups | Seeds | Total episodes |
|---|---|---|---|---:|
| Luna, Haiku 5.5; medium reasoning | `none`, `public`, `leader` | 0 and 1, reported separately | 0–11 | 144 |

Each episode has **6 players, 20 rounds, and neutral personalities**. The full matrix contains **8,640 encounters and 35,424 generation requests before retries**. Each episode uses 246 requests; histories and reasoning tokens also contribute to API usage.

For additional CLI options:

```bash
uv run --frozen --no-editable intentional-experiments --help
uv run --frozen --no-editable intentional-experiments matrix --help
```

## Run experiments

### Configure access

For hosted runs, set `OPENROUTER_API_KEY` in your shell or a root `.env` file. For example, edit `.env` locally to contain:

```dotenv
OPENROUTER_API_KEY=your-key-here
```

Keep your real key out of Git and shared output archives. The CLI reads `.env`, and existing shell values take precedence. The runner sends Luna requests to OpenAI and Haiku requests to Anthropic through OpenRouter, disables fallbacks, and checks model capabilities before generation.

### Preview a smaller cohort

One seed still includes both models, all three communication modes, and both role groups: **12 episodes and 2,952 generation requests before retries**.

```bash
uv run --frozen --no-editable intentional-experiments matrix --seeds 0
```

### Explicitly launch a hosted cohort

**The following commands use OpenRouter credits.** Choose the cohort you intend to run; adding `--execute` starts it.

One matched seed:

```bash
uv run --frozen --no-editable intentional-experiments matrix \
  --seeds 0 \
  --output results/luna-haiku-seed-0 --execute
```

Full 12-seed matrix:

```bash
uv run --frozen --no-editable intentional-experiments matrix \
  --config configs/experiment_matrix.json \
  --output results/luna-haiku-full --execute
```

Episodes execute sequentially. Coordinate seed assignments with the team and give each independent cohort its own output directory. One process owns each output directory. Keep every model/communication cell for a seed together so the analyzer can form matched comparisons.

For an **optional offline mechanics check**, use scripted policies:

```bash
uv run --frozen --no-editable intentional-experiments matrix \
  --backend scripted --seeds 0 \
  --output results/scripted-check --execute
```

Scripted output exercises the pipeline without hosted-model requests. Its `backend` field identifies it as synthetic data.

### Customize a new cohort

Copy [configs/experiment_matrix.json](configs/experiment_matrix.json) to a new JSON file, edit the supported settings, and preview it:

```bash
uv run --frozen --no-editable intentional-experiments matrix \
  --config configs/my-study.json
```

The config lists model IDs, communication modes, selfish-player counts, seeds, and shared game settings. This study fixes medium reasoning and neutral personalities. Change the configuration before starting a new cohort; an interrupted run requires its original settings.

### Resume an interrupted run

Use the run's saved `spec.json` so seed and backend overrides carry forward:

```bash
uv run --frozen --no-editable intentional-experiments matrix \
  --config results/luna-haiku-seed-0/spec.json \
  --output results/luna-haiku-seed-0 --execute --resume
```

The runner checkpoints accepted responses and completed phases. Resumption reuses them, including completed episodes. It stops on configuration or source drift. Invalid outputs receive one correction attempt; persistent failures leave checkpoints and a partial report. Transport retries are bounded; a response lost before durable recording can require another billed request.

If the application source has changed, use the saved runtime with the original dependency environment:

```bash
PYTHONPATH=results/luna-haiku-seed-0/runtime \
  .venv/bin/python -m swarm_game.cli matrix \
  --config results/luna-haiku-seed-0/spec.json \
  --output results/luna-haiku-seed-0 --execute --resume
```

## Visualization quickstart

Start developing immediately with the committed fixtures:

- [Complete synthetic bundle](docs/visualization/examples/complete.json): both model labels and all communication conditions.
- [Incomplete synthetic bundle](docs/visualization/examples/incomplete.json): missing final scores and empty tables.
- [Generated TypeScript types](docs/visualization/types.ts).
- [JSON Schema](docs/visualization/visualization.schema.json).
- [Full data contract and parsing guide](docs/visualization/README.md).

For actual results, read **`RUN_DIRECTORY/visualization.json`**. Every condition uses schema version **`intentional-agent.visualization/1`**, with fixed fields, explicit nulls, stable IDs, and an atomic snapshot.

A Python reader can validate a bundle and access a table:

```python
from swarm_game.export_contract import load_bundle

# Replace this fixture path with a saved run's visualization.json when ready.
bundle = load_bundle("docs/visualization/examples/complete.json")
episodes = bundle["tables"]["episodes"]
completed = [row for row in episodes if row["status"] == "complete"]
actions = bundle["tables"]["actions"]
```

For frontend development, use the generated TypeScript types and JSON Schema at ingestion. Serve the JSON through your team's data route; the CLI writes files rather than starting a web server.

Use `(run_id, episode_id)` to join episode tables. Keep zero/one-selfish groups separate, filter final-score charts to completed episodes, and retain `backend` so scripted fixtures stay distinguishable from hosted-model results. Treat private notes, ballots, and true roles as observer data.

The existing dashboard uses its original protocol. Build this study's visualizations against the versioned bundle above; [legacy workflows](docs/legacy-workflows.md) describe the older interface.

## Analyze and share results

These commands operate on saved files and make no model calls:

```bash
uv run --frozen --no-editable intentional-experiments analyze \
  results/luna-haiku-seed-0

uv run --frozen --no-editable intentional-experiments validate-output \
  results/luna-haiku-seed-0
```

Open the run's `report.html` or `report.md` for a summary. Use `visualization.json` for the stable machine interface. The validator checks schema, identifiers, field types, and agreement among the JSON, CSV, and timeline exports.

For a visualization handoff, share `visualization.json` and `visualization.schema.json`; include `report.html` for quick review. For reproducibility or resumption, archive the **entire run directory**, including `spec.json`, manifests, `output_identity.json`, `runtime/`, checkpoints, and raw request logs. Record the launch commit (`git rev-parse HEAD`) when coordinating a cohort.

Generated `results/` directories stay outside Git. Share them through the team's agreed artifact storage. The analyzer compares episodes within one run directory; it does not automatically pool separate collaborators' cohorts. Preserve each cohort's identity when combining data downstream.

## Contribute changes

Create a feature branch and run the relevant checks:

```bash
git switch -c your-name/short-description
uv run --frozen --extra dev --no-editable pytest -q
```

Tests use synthetic policies and mocked responses. Two Docker integration tests require a running Docker daemon; CI requires both to execute. For dashboard changes, also run:

```bash
npm --prefix frontend ci
npm --prefix frontend run build
```

Useful entry points:

| Change | Files |
|---|---|
| Cohort dimensions | [configs/experiment_matrix.json](configs/experiment_matrix.json) |
| Matching, elections, and visibility | [game.py](backend/swarm_game/game.py) |
| Agent instructions and output validation | [prompts/](backend/swarm_game/prompts/), [protocol.py](backend/swarm_game/protocol.py) |
| Provider calls and routing | [providers.py](backend/swarm_game/providers.py) |
| Scores and comparisons | [analysis.py](backend/swarm_game/analysis.py), [matrix_analysis.py](backend/swarm_game/matrix_analysis.py) |
| Visualization schema and serialization | [export_contract.py](backend/swarm_game/export_contract.py) |
| Regression tests | [tests/swarm/](tests/swarm/) |

When changing the visualization contract, follow its [versioning rules](docs/visualization/README.md#file-consistency-and-compatibility) and regenerate the schema and types:

```bash
uv run --frozen --no-editable python scripts/generate_output_contract.py
```

Open a pull request describing the behavior change and checks you ran. Keep historical pilot records and frozen run snapshots intact. Changes to prompts or game rules define a new experimental setting and should use a fresh cohort.

## Experiment design

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

<a id="unified-outputs"></a>

## Output reference

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

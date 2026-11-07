# Intentional Agent — collaborator guide

Study **Luna** across **no communication, full communication, opponent-only communication, a predetermined good leader, and a predetermined selfish leader** in a rotating Prisoner's Dilemma. This repository provides one runner, reproducible configurations, and a versioned output contract for the visualization team.

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
| Luna; medium reasoning | `none`, `public`, `opponent`, `good_leader`, `selfish_leader` | 1, 3, and 5, reported separately | 0–11 | 180 |

Each episode has **10 players, 10 rounds, and neutral personalities**. The design crosses **1 model × 5 communication modes × 3 selfish-player counts × 12 seeds**, for **180 episodes, 9,000 encounters, and 37,800 generation requests before retries**. Every episode uses **210 requests**: 10 players each provide 10 messages or private notes, 10 actions, and one final private report. Histories and reasoning tokens also contribute to API usage.

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

Keep your real key out of Git and shared output archives. The CLI reads `.env`, and existing shell values take precedence. The runner sends Luna requests to OpenAI through OpenRouter, disables fallbacks, and checks model capabilities before generation. Optional Haiku ablations route to Anthropic.

### Preview a smaller cohort

One seed includes Luna, all five communication modes, and all three selfish-player counts: **15 episodes and 3,150 generation requests before retries**.

```bash
uv run --frozen --no-editable intentional-experiments matrix --seeds 0
```

### Explicitly launch a hosted cohort

**The following commands use OpenRouter credits.** Choose the cohort you intend to run; adding `--execute` starts it.

One matched seed:

```bash
uv run --frozen --no-editable intentional-experiments matrix \
  --seeds 0 \
  --output results/luna-seed-0 --execute
```

Full 12-seed matrix:

```bash
uv run --frozen --no-editable intentional-experiments matrix \
  --config configs/experiment_matrix.json \
  --output results/luna-full --execute
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

### Optional model ablations

The main study uses Luna alone. [configs/model_ablation.json](configs/model_ablation.json) preserves the matched Luna–Haiku comparison as an opt-in ablation: 360 episodes and 75,600 requests before retries. Preview it with:

```bash
uv run --frozen --no-editable intentional-experiments matrix \
  --config configs/model_ablation.json
```

An explicitly launched ablation needs its own output directory. The model registry also supports `openai/gpt-6.1-terra` and `openai/gpt-6-astra`; add them to a separate ablation configuration when required. Keep Luna as the baseline when using within-run model contrasts. The default main-study launch selects only Luna.

### Split the main study across three computers

Use the [three computer launch prompts](docs/launch-prompts.md). Assign selfish counts 1, 3, and 5 to computers 1, 2, and 3 respectively. Each computer runs Luna across all five conditions and seeds 0–11: **60 episodes, 3,000 encounters, and 12,600 requests before retries**. The selfish identities and encounter schedules remain matched across conditions within each seed; identities may change between seeds. Keep each computer's config, logs, and output directory separate.

### Resume an interrupted run

Use the run's saved `spec.json` so seed and backend overrides carry forward:

```bash
uv run --frozen --no-editable intentional-experiments matrix \
  --config results/luna-seed-0/spec.json \
  --output results/luna-seed-0 --execute --resume
```

The runner checkpoints accepted responses and completed phases. Resumption reuses them, including completed episodes. It stops on configuration or source drift. Invalid outputs receive one correction attempt; persistent failures leave checkpoints and a partial report. Transport retries are bounded; a response lost before durable recording can require another billed request.

If the application source has changed, use the saved runtime with the original dependency environment:

```bash
PYTHONPATH=results/luna-seed-0/runtime \
  .venv/bin/python -m swarm_game.cli matrix \
  --config results/luna-seed-0/spec.json \
  --output results/luna-seed-0 --execute --resume
```

## Visualization quickstart

Start developing immediately with the committed fixtures:

- [Complete synthetic bundle](docs/visualization/examples/complete.json): Luna and the optional Haiku ablation label, with all communication conditions.
- [Incomplete synthetic bundle](docs/visualization/examples/incomplete.json): missing final scores and empty tables.
- [Generated TypeScript types](docs/visualization/types.ts).
- [JSON Schema](docs/visualization/visualization.schema.json).
- [Full data contract and parsing guide](docs/visualization/README.md).

For actual results, read **`RUN_DIRECTORY/visualization.json`**. Every condition uses schema version **`intentional-agent.visualization/4`**, with fixed fields, explicit nulls, stable IDs, and an atomic snapshot.

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

Use `(run_id, episode_id)` to join episode tables. Keep the 1-, 3-, and 5-selfish-player groups separate, filter final-score charts to completed episodes, and retain `backend` so scripted fixtures stay distinguishable from hosted-model results. Treat private messages, notes, ballots, and true roles as observer data.

The existing dashboard uses its original protocol. Build this study's visualizations against the versioned bundle above; [legacy workflows](docs/legacy-workflows.md) describe the older interface.

## Analyze and share results

These commands operate on saved files and make no model calls:

```bash
uv run --frozen --no-editable intentional-experiments analyze \
  results/luna-seed-0

uv run --frozen --no-editable intentional-experiments validate-output \
  results/luna-seed-0
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
| Matching, predetermined leaders, and visibility | [game.py](backend/swarm_game/game.py) |
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
| Main model | `openai/gpt-6-luna` |
| Optional model ablations | Haiku 5.5, Terra, or Astra; configure explicitly in a separate cohort |
| Reasoning | `medium` for the main study and model ablations |
| Communication axis | `none`, `public`, `opponent`, `good_leader`, `selfish_leader` |
| Selfish-player count axis | 1, 3, or 5 selfish players; analyze separately |
| Population / horizon | 10 players, 10 rounds |
| Replications | 12 matched seeds, 0–11 |
| Personalities | Neutral for everyone |
| Primary outcome | Total cumulative payoff of actual good players |

All players in an episode use the same model. A good player maximizes the collective payoff of actual good players; each selfish player maximizes its own payoff and may cooperate or lie. Players know their own objective and an equal prior over 1, 3, and 5 selfish players before role assignment. They condition that prior on their own role. Other objectives, fellow selfish players, and the realized count stay hidden. A fixed seeded role ordering gives nested selfish rosters across counts and identical rosters across models and communication modes within each count.

Agents report a marginal probability for each player's selfish role. Multiple players can have high probabilities simultaneously; the sum represents the expected selfish-player count and lies between 1 and 5. Reports include each player's known own role and omit the `none` category. Analysis scores good agents' reports with the mean binary Brier score over other players and measures final identification across all good-agent/selfish-target pairs.

Every round matches each player with exactly one opponent. Seeded round-robin cycles give everyone every opponent once per nine rounds; round 10 starts a new cycle. Payoffs: CC=(3,3), DC=(5,0), CD=(0,5), DD=(1,1). The runner collects all actions before resolving them and reveals each encounter only to its participants.

### Communication and predetermined leaders

| Condition | Before every round, including round 1 |
|---|---|
| `none` | Everyone writes a private note |
| `public` | Everyone broadcasts to all players |
| `opponent` | Each player privately messages that round's opponent |
| `good_leader` | Only the predetermined good leader broadcasts; everyone else writes a private note |
| `selfish_leader` | Only the predetermined selfish leader broadcasts; everyone else writes a private note |

Communication rules:

- The engine predetermines a leader before gameplay using a separate seeded draw among players with the required role. That player remains leader for all 10 rounds. The protocol has no election or midpoint reflection.
- Both leader conditions appear to agents as **leader communication**. Agents see the leader's identity; only observer records identify the good/selfish condition and leader's role. Each player continues to know its own objective.
- The audience judges the leader using its own encounters and permitted messages. Each player sees only its own playing history. Leadership grants speaking permission; everyone still chooses their own actions and pursues their own objective.
- Before every round, all players submit one message or private note. The engine delivers permitted messages together before anyone chooses an action. Opponent messages reach only the sender and that round's opponent; private notes remain visible only to their author.
- Each message or note permits 96 `o200k_base` content tokens. Every condition has the same deliberation opportunities and request count. A final private belief report follows round 10.
- Sender IDs are authentic. Message claims remain unverified, and every player may lie. Leader roles describe objectives rather than a prescribed action or speaking style.

Within each selfish-count/seed combination, every condition and model uses identical schedules, roles, and player identities. Good-leader and selfish-leader conditions can designate different players; each designation stays fixed across models for the same condition and seed. The runner randomizes execution order within each seed block. Seeds control the design, not hosted-model responses. The shared `medium` setting does not guarantee identical reasoning-token expenditure across providers.

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
| `messages.csv` | Public messages, opponent messages, and private notes, with explicit visibility |
| `leader_assignments.csv` | Predetermined leader identity and role; observer-only, available from setup |
| `elections.csv` | Historical election ballots; empty for the final five-condition protocol |
| `usage.csv`, `status.csv` | Response attempts, cost, provider metadata, and missing/incomplete cells |
| `events.csv`, `timeline.jsonl` | Fixed event envelopes with typed payloads and stable sequence IDs |
| `episodes/*/` | Checkpoints, exact permitted prompts, responses, and episode reports |
| `runtime/` | Saved runner, prompts, and dependency provenance |

The visualization contract is `intentional-agent.visualization/4`; the matrix manifest uses `intentional-experiments/1`, and the experimental protocol is `rotating-v4`. Exports include all `selfish_players`, the `belief_format`, opponent recipients, predetermined leader assignments, and the `pre_round` phase. Report normalized good return as total good payoff divided by `rounds × good_player_count`. The good-player count is 9, 7, or 5 for the three role groups. Other metrics include good–good/good–selfish contributions, cooperation, binary Brier scores, identification at 0.8, false accusations, and first/second-half return. The existing `pre_midpoint`/`post_midpoint` metric names identify those halves; they imply no election in this protocol.

Contrasts match complete seed blocks and retain separate 1-, 3-, and 5-selfish-player groups. They compare communication within each model and models within each communication condition. Bootstrap intervals resample seed blocks; they use 10,000 resamples and remain null with fewer than two pairs. Missing cells remain explicit, and cost summaries include failed/incomplete episodes. Collective return and identification measure distinct outcomes; cooperative selfish players can improve return without becoming identifiable.

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

`swarm-game` remains an alias for `intentional-experiments`. Historical `compare`/`pilot` commands retain `rotating-v1` (240 requests per default episode); `rotating-v2`/`rotating-v3` retain their legacy midpoint protocols. Current single-episode `run` defaults to `rotating-v4`, 10 players, 10 rounds, and one selfish player; `--selfish-count 3` or `5` selects another role group, and `--communication` selects one of the five conditions. Historical runs retain their recorded prompts, frozen runtimes, and output formats; resume them with their saved runtime. The new matrix keeps their results separate.

The existing dashboard and IPD entry points remain available for their original protocols; the matrix CLI above is the canonical path for this study. All packages now share the root install and payoff definition. See [legacy workflows](docs/legacy-workflows.md) for the original interfaces and [recorded pilots](experiments/swarm-game/records/README.md) for prior results. Do not treat the historical Trump-like persona pilot as a neutral Haiku/Luna matrix cell.

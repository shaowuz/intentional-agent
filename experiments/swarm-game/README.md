# Communication and collective return

This runner compares **no communication** with **public communication** in a rotating
Prisoner's Dilemma. The Python engine runs on your machine and calls
**OpenAI GPT-6 Luna through OpenRouter** (`openai/gpt-6-luna`, medium reasoning).
Single runs, comparisons, and smoke checks also accept an explicit
`--model openai/gpt-6.1-terra` or `--model openai/gpt-6-astra`.
Each experiment uses one fixed model.

## Setup

The project pins Python 3.11. Install Python and uv, then use
`--no-editable` for installation and execution: iCloud marks `.pth` files inside
`.venv` as hidden, and Python skips those editable-install hooks. A regular package
installation works without those hooks.

```sh
uv sync --locked --no-editable
```

Set `OPENROUTER_API_KEY` in your shell or in the workspace `.env`. The CLI reads
`.env` automatically; existing environment values take precedence. `.env.example`
lists the variables. Preserve your existing `.env`; keep it out of version control.
Only `https://openrouter.ai/api/v1` is an accepted API destination.

The fixed `o200k_base` tokenizer downloads its public data on first use and then
uses its local cache. This tokenizer defines the experimental message budget;
provider billing token counts may differ. `uv.lock` pins the dependencies.

## Commands

Run a scripted comparison of all four conditions, without model calls:

```sh
uv run --no-editable swarm-game compare --backend scripted --seeds 1 --output runs/scripted-demo
```

Run the bounded integration check (four independent GPT-6 fixtures, at most four
generation requests, no retries):

```sh
uv run --no-editable swarm-game smoke --output runs/gpt6-smoke
```

Run a single live episode, or a matched four-episode comparison:

```sh
uv run --no-editable swarm-game run --communication public --selfish-count 1 --seed 0 --output runs/public-0
uv run --no-editable swarm-game compare --seeds 1 --output runs/comparison-0
```

Default episodes have 6 players, 20 rounds, 60 encounters, and 240 model requests
before retries. `--players` accepts even counts of at least 2; `--rounds` accepts
positive counts. A partial final rotation is allowed. The CLI exposes
`--communication none|public`, `--selfish-count 0|1`, and `--seed` for single runs.

Resume with the same installed source and dependencies, or rebuild analysis:

```sh
uv run --no-editable swarm-game resume runs/public-0
uv run --no-editable swarm-game compare --seeds 1 --output runs/comparison-0 --resume
uv run --no-editable swarm-game analyze runs/comparison-0
```

Preview the 48-episode pilot and explicitly launch it separately:

```sh
uv run --no-editable swarm-game pilot
uv run --no-editable swarm-game pilot --execute --output runs/pilot
```

The preview makes no model calls. The pilot has **2 modes × 2 role counts × 12
matched seeds**, **2,880 encounters**, and **11,520 requests before retries**.
The `--execute` flag starts the full workload using your OpenRouter credits.
Track actual token usage and reported cost in run outputs. A 96-token post budget
does not cap the provider's hidden reasoning or cumulative input tokens.

The requested Luna persona repeat uses public communication only: **24 episodes**,
12 matched seeds with zero or one selfish player, 1,440 encounters and 5,760
accepted model responses. The selfish player receives a fictional, Trump-like
rhetorical persona emphasizing forceful persuasion, boasting, and strategic
deception. Its objective remains its own cumulative payoff; it can cooperate.
Good agents receive no persona instruction or notice of its assignment. All agents
receive the same explicit arithmetic guidance for valid probability reports.

```sh
uv run --no-editable swarm-game pilot --config configs/pilot_luna_persona_public.json
uv run --no-editable python scripts/run_pilot.py --config configs/pilot_luna_persona_public.json --workers 24 --output runs/pilot-luna-persona-public-2026-11-07-v2
```

The concurrent launcher freezes the installed runner, prompts, configuration, and
dependency lock before making requests. Use the same launch command with `--resume`
to reuse that snapshot and saved responses. A single episode accepts
`--selfish-persona trump_like`; the default is `neutral`.
This public-only repeat measures outcomes under the combined model/persona setting.
A comparison with the earlier Terra pilot cannot isolate the personality effect.

Belief reports are model-generated estimates. The runner checks their ranges and
sum; it does not calculate a Bayesian posterior for the agents. For this Luna
repeat, the user authorized one additional arithmetic-only model repair after the
standard correction failed. The helper preserves the last action, strategy text,
and player-ID probabilities and requests the exact residual probability for `none`.
It retains the original responses and a separate recovery receipt. Preview a
stopped episode's proposed repair without making a model request:

```sh
uv run --no-editable python scripts/repair_belief_request.py RUN_DIRECTORY/EPISODE_DIRECTORY
```

`--execute --resume-episode` applies that explicitly authorized repair and resumes
the saved episode. Each failed response permits at most one additional attempt.
The first launch and its numerical-format failure remain in
`runs/pilot-luna-persona-public-2026-11-07`; the final cohort uses the separate `-v2`
directory. Its `results/REPORT.md` and `agent_traces/README.md` provide outcomes and
all recorded strategy summaries, beliefs, and messages.

## Rules and prompts

- Every round partitions players into disjoint pairs. Each player chooses C or D
  once. Both choices commit before either player observes the outcome.
- Payoffs: CC=(3,3), DC=(5,0), CD=(0,5), DD=(1,1). Actions execute exactly.
- A randomized round-robin cycle lasts N−1 rounds; each pair meets once per cycle.
  Each new cycle randomizes identity order and round order independently of roles.
- Good players optimize the total cumulative payoff of actual good players.
  The selfish player optimizes its own payoff and may cooperate throughout.
- The episode-level prior gives zero or one selfish player equal probability.
  Everyone knows their own objective. A good player's conditional prior at N=6
  is P(none)=6/11 and P(each other player selfish)=1/11.
- Each player sees its own encounters, current opponent, and permitted discussion.
  Future pairings, other objectives, and the good-team total remain hidden.
- After rounds 1 through T−1, each player writes either a private note (`none`)
  or a public post (`public`). Each content string permits 96 `o200k_base` tokens.
  The engine delivers all posts together after collection. It authenticates sender
  IDs and delivers claims unchanged, including lies. Empty posts are valid.
- Players receive their full permitted history, including their previous private
  belief and strategy reports. Each request uses a fresh, explicit message list.
  Requests expose no tools, filesystem, shared model conversation, or evaluator state.

Readable templates live in `src/swarm_game/prompts/`. Action responses include
private identity probabilities and a strategy summary of at most 300 characters.
Probabilities cover `none` and all IDs, sum to 1, and respect the player's known
own role. A final private report follows the last encounter. The engine never
publishes these belief reports automatically. Repeated belief elicitation may
influence behavior; both conditions use the same procedure.

The no-communication condition includes a private note to match the public
condition's extra deliberation opportunity. This controls call count and outgoing
content budget. Public discussion naturally supplies more incoming information.

## Outputs and recovery

Each episode directory contains:

| File | Contents |
|---|---|
| `manifest.json` | Configuration, source/prompt hashes, dependency and Python versions |
| `checkpoint.json` | Observer state, roles, full schedule, pending decisions, results |
| `requests/*.json` | Exact player views/prompts, response attempts, provider metadata, usage/cost |
| `summary.json` | Returns, cooperation, belief scores, identification, usage |
| `timeline.jsonl` | Actions, private belief/strategy trajectories, notes and public messages |
| `report.md` | Human-readable observer transcript |
| `error.json` | Most recent blocking error, when present |

These files belong to the observer and include private information. The engine
builds model inputs from an explicit player-view allowlist. It never sends output
directories or full checkpoints to agents. Credential headers never enter logs;
the writer also redacts the configured key and key-shaped strings.

The runner atomically saves each accepted response before advancing the game and
checkpoints each phase. Resuming reuses saved responses. A process interruption
between a provider accepting a request and the local response write can cause a
repeat API request; no client-side checkpoint can guarantee exactly-once billing.
The engine locks episode directories against concurrent writers and refuses to
overwrite existing episodes or resume with changed code/configuration.

Transient transport, 429, and 5xx failures allow three HTTP attempts per generation.
Invalid JSON/schema, belief totals, or message lengths allow one formatting correction.
Persistent failures stop the episode; the engine never substitutes an action.
Model/provider changes fail explicitly. OpenAI-only routing, disabled fallbacks,
and `require_parameters=true` preserve the requested model settings. Resume can
retry transport failures; exhausted formatting attempts remain failed for inspection.

## Analysis

The primary outcome is **total good-agent return**, reported separately for zero
and one selfish player. Normalized return divides by T×number of good players.
Good–good and good–selfish components include only good players' payoffs.

The analysis reports cooperation rates, multiclass Brier scores (sum of squared
probability errors), final identification at probability ≥0.8, false accusations
against actual good opponents, and identification before personal contact. Action
beliefs precede that round's encounter; final beliefs follow the final encounter.
The final Brier score gives one observation per good player. Pooled belief scores
describe trajectories and do not create independent statistical samples.

Comparison outputs include `episodes.csv`, `comparison.json`, and `report.md`.
Effects use public minus none within matched seed blocks. For at least two blocks,
the normalized effect includes an exploratory 95% percentile interval from 10,000
whole-block bootstrap resamples. One-block comparisons have no interval. Failed
and unmatched cells appear explicitly in the report; they do not enter paired effects.
Model responses remain stochastic even when schedules and roles use fixed seeds.

Use timelines to investigate retaliation, forgiveness, reputation building, and
selective exploitation. Short self-reports supplement observed actions; they do
not establish a causal strategy. Cooperative selfish agents can improve welfare
while remaining hard to identify. Good agents can rationally exploit selfish agents.

Scripted `cooperate`, `defect`, and `tit_for_tat` policies validate mechanics.
`--policy` selects the good policy; `--selfish-policy` selects the selfish policy.
Tit-for-tat starts with C and copies that opponent's most recent past action.
Scripted results do not establish how GPT-6 behaves.

## Verification

```sh
uv run --no-editable pytest
uv run --no-editable ruff check src tests
```

Tests cover payoffs, rotations, private information, simultaneous delivery, false
messages, cooperative selfish agents, known policy scores, matched conditions,
malformed responses, interrupted-run recovery, provider restrictions, redaction,
CLI commands, and the four-request smoke protocol using mocked HTTP responses.

API references: [GPT-6 Luna on OpenRouter](https://openrouter.ai/openai/gpt-6-luna/),
[structured outputs](https://openrouter.ai/docs/guides/features/structured-outputs),
[provider routing](https://openrouter.ai/docs/guides/routing/provider-selection).

## Completed pilot records

[Browse the recorded experiments](records/README.md): the 48-episode Terra pilot
and the 24-episode Luna persona/public repeat, with their original configurations,
frozen runtimes, checkpoints, reports, plots, and all agent transcripts.
The raw API request/response files are losslessly compressed in each run's
`raw-requests.tar.xz`; extract them into that run directory to rebuild analysis or
inspect individual requests. The excluded preliminary Luna attempt is retained
separately and contributes no outcomes to the completed repeat.

```sh
tar -xJf records/pilot-luna-persona-public-2026-11-07-v2/raw-requests.tar.xz -C records/pilot-luna-persona-public-2026-11-07-v2
```

Published reports replace machine-local file references with repository links.
Raw request JSON, checkpoints, and frozen source retain their original bytes.
`publication_manifest.json` records source and published hashes for each file.
The independent dashboard at the repository root uses its own protocol; these
command-line experiments retain the rules and exact prompts documented here.

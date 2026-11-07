# intentional-agent

This repository contains three complementary implementations for studying the
Iterated Prisoner's Dilemma with LLM agents:

- **Local research dashboard** (`backend/`, `frontend/`, `docs/`) -- an
  interactive web application with private agent objectives, optional public
  discussion, and controlled tools. See **Part 1** below and
  `docs/user-guide.md`.
- **Python IPD experiment package** (`ipd/`, `config/`, `scripts/`) -- a
  scriptable, reproducible experiment for studying how initial beliefs (priors)
  affect the emergence and evolution of cooperation, with mock/real LLM backends,
  JSONL recording, checkpoint/resume, analysis and plots. See **Part 2** below
  and `PILOT_REPORT.md`.
- **OpenRouter swarm-game pilots** (`experiments/swarm-game/`) -- the rotating
  six-player experiments with zero or one selfish player, exact prompts,
  recorded Terra/Luna results, and complete agent transcripts. See **Part 3** below.

Each part has its own runtime requirements (Part 1: Python 3.11+ / Node 22+;
Part 2: Python 3.9+ with `requirements.txt`; Part 3: Python 3.11+ with its own
`pyproject.toml` and `uv.lock`).

# Part 1 -- Local research dashboard (`backend/`, `frontend/`)

A local research dashboard for repeated Prisoner's Dilemma experiments with private agent objectives, optional public discussion, and controlled tools.

Group 1 agents seek to maximize their collective's cumulative game payoff. Group 2 agents each seek to maximize their own cumulative payoff. Agents know their own objective but are not given other agents' group memberships or objectives. The researcher can inspect the full experiment.

## Run locally

Requirements: **Python 3.11+**, **Node.js 22+**, and npm. [uv](https://docs.astral.sh/uv/getting-started/installation/) is recommended; the startup script also supports a Python virtual environment without uv.

```bash
git clone https://github.com/shaowuz/intentional-agent.git
cd intentional-agent
./scripts/dev.sh
```

Open **http://127.0.0.1:8000**. The script installs dependencies, builds the dashboard, and starts one local API worker. It does not publish a website.

1. Create a local researcher account.
2. Create an experiment in **Scripted demo** mode. Start with 4 agents and 20 rounds.
3. Start the run or advance one round at a time. Inspect pairings, payoffs, observations, and the forum when enabled.
4. Export the JSON record or CSV match ledger.

**Scripted demo is synthetic behavior for checking the framework, not an LLM experiment.** It requires neither an API key nor Docker and makes no paid inference requests.

## Run real agents

In **API Settings**, enter your own OpenRouter API key. Create an **OpenRouter** experiment, choose a tool-capable model for each populated group, set a budget, and start the run. Different researchers use their own keys and own their experiment records.

Keys are held in server memory. They are not saved in the database, agent workspaces, browser storage, or exports. Re-enter your key after restarting the server. The browser stores only a session token for authentication.

For Python execution, install and start Docker, then prepare the sandbox image:

```bash
docker pull python:3.12-slim
```

Agent code runs in a restricted Docker container with networking disabled and only that agent's workspace available. There is no host-execution fallback. File tools preserve an agent's files across rounds of one experiment; workspaces do not carry over to new experiments. If Docker is unavailable, the application reports that Python execution is unavailable.

**Internet access** separately enables web search and webpage reading. Search uses the same researcher's OpenRouter key through a separate web-enabled request; ordinary agent calls do not automatically search. It does not enable networking inside the Python container. Enabling forum access or global history does not enable internet access.

## Experiment rules

| Setting | Initial behavior |
| --- | --- |
| Population | 4 agents: 3 in Group 1, 1 in Group 2; configurable |
| Horizon | 20 fixed rounds, disclosed to agents; configurable |
| Matching | Seeded random pairs each round; an odd population gives one bye |
| Actions | `C` or `D`, collected before simultaneous reveal |
| Payoffs | `CC: (3,3)`, `CD: (0,5)`, `DC: (5,0)`, `DD: (1,1)` |
| Personal history | Opponent ID, both actions, own round payoff and cumulative payoff |
| Public forum | Off by default; when enabled, posts and replies follow settlement |
| Global history | Off by default; when enabled, exposes settled matches, not hidden roles |
| Collective score feedback | Off by default; Group 1's aggregate payoff is researcher-only |
| Internet tools | Off by default; search and read are separate from offline code execution |

Both groups share the common game instructions and receive their own private objective. Prompts are editable. Group 2 is not automatically instructed to deceive, and the engine does not force any group to cooperate or defect.

For an objective comparison, start with the **same model and parameters in both groups**. Changing both objective and model changes two factors. Hidden membership means the system withholds labels; agents may still infer membership from behavior. A random seed reproduces the environment's scheduling, not necessarily LLM outputs.

## Controls, records, and costs

- Start, pause at a checkpoint, resume, advance one round, or stop. A stopped experiment cannot restart.
- Failed or invalid decisions pause the run; they are never replaced with an invented `C` or `D`.
- JSON exports include configuration, observations, messages, tools, actions, payoffs, and usage. CSV exports contain the match ledger.
- The inspector shows information actually supplied to agents and returned by the API. It does not claim access to hidden model reasoning.
- Budget checks limit new requests. Provider charges, requests already in flight, retries, and missing usage reports mean the configured budget is not an absolute billing guarantee. Search can incur additional charges; failed requests may also be billed.
- If a charge is unconfirmed, further requests stop. Review the run's charges in OpenRouter, then use **Reconcile Usage** while the run is idle to enter the verified total cost and a note. The adjustment is recorded for audit; unknown charges are never automatically treated as zero.

State is stored in `.data/` by default. Keep that directory private; it contains experiment records and password hashes. It is excluded from Git. A server restart pauses interrupted runs and clears the in-memory API keys. Review the checkpoint and usage before resuming.

## Development and verification

```bash
./scripts/check.sh
```

The check script runs Python tests and the TypeScript/production build. Docker integration tests explicitly skip when no daemon is available. With a running daemon, a missing image is an error: prepare it with the pull command above. CI prepares Docker and requires the isolation tests to execute without skips. OpenRouter adapter tests use mocked HTTP responses; passing them is not evidence that a paid model experiment ran.

For frontend hot reload, run the backend in one terminal and Vite in another:

```bash
uv run uvicorn intentional_agent.main:app --host 127.0.0.1 --port 8000
```

```bash
cd frontend
npm run dev
```

Vite serves http://127.0.0.1:5173 and proxies `/api` to the backend. API documentation is available at http://127.0.0.1:8000/docs.

See [the user guide](docs/user-guide.md) for setup fields, permissions, and recovery. This MVP targets a local or single-server pilot; internet-facing hosting, large-population performance, and production hardening remain separate work.

# Part 2 -- Python IPD experiment (`ipd/`)

A reproducible, multi-agent experiment studying how **initial beliefs (priors)**
affect the spontaneous emergence and evolution of cooperation in the **Iterated
Prisoner's Dilemma (IPD)**.

All agents use the same configurable LLM and identical instructions and differ
**only** in their initial prior about the probability that a new opponent defects
in the first round. Agents are not given any strategy or belief-updating rule;
they must develop their own behaviour from experience.

This repository contains the full implementation, configuration files, tests,
raw-data recording, analysis/plotting scripts, checkpoint/resume support and a
generated research report.

---

## Feature checklist (mapped to the specification)

| Requirement | Where |
|---|---|
| IPD payoff matrix (3/0/5/1) | `ipd/game.py` |
| Fixed (20) and random (p=0.95) horizons | `ipd/game.py`, `ipd/tournament.py` |
| 5 prior groups (0.1 … 0.9), 10 agents each | `ipd/config.py`, `config/full.yaml` |
| Identical prompts except the prior | `ipd/prompts.py` |
| Random pairing, avoiding repeats | `ipd/pairing.py` (seeded round-robin) |
| Simultaneous, independent actions | `ipd/tournament.py::play_match` |
| Opponent identities never revealed | `ipd/memory.py`, `ipd/prompts.py` |
| Complete, lossless structured memory (full action strings; all rounds) | `ipd/memory.py` |
| End-of-game belief estimate about new opponents | `ipd/prompts.py`, `ipd/agent.py` |
| No prescribed strategy / updating rule | prompt only asks for an action + JSON |
| Raw JSONL recording (actions, payoffs, histories, beliefs) | `ipd/recorder.py` |
| Reproducible seeds | `ipd/utils.py::derive_seed` |
| Checkpoint / resume | `ipd/recorder.py`, `ipd/tournament.py` |
| API usage + cost tracking | `ipd/usage.py` |
| Configurable provider/model | `ipd/llm/`, `ipd/config.py` |
| Tests (pairing, simultaneity, payoff, termination, memory isolation, …) | `tests/` |
| Analysis + plots + uncertainty | `ipd/analysis.py` |
| Mock backend for offline testing | `ipd/llm/mock.py` |

---

## Requirements

Python 3.9+. Install dependencies:

```bash
python3 -m pip install -r requirements.txt
```

Libraries used: `PyYAML`, `numpy`, `pandas`, `matplotlib`, `requests`. No LLM
vendor SDK is required; API calls use plain `requests`.

---

## Quickstart (offline, mock backend)

```bash
# 1. Run the tiny smoke experiment (mock backend, no API key needed)
python3 -m ipd.cli run --config config/smoke.yaml

# 2. Validate the raw data for internal consistency
python3 scripts/validate_run.py --results results/smoke

# 3. Analyse: writes tables/, figures/ and report.md
python3 -m ipd.cli analyze --results results/smoke

# 4. Run the ipd test suite
bash scripts/run_tests.sh
```

Use `python3 -m ipd.cli run` and `python3 -m ipd.cli analyze` as the experiment
entry points.

---

## Running the real-LLM pilot (required before the full experiment)

The pilot is **2 agents per prior group (10 agents), 2 games per agent, both
horizon conditions**. Set your key and run:

```bash
export OPENAI_API_KEY=sk-...            # or ANTHROPIC_API_KEY
python3 -m ipd.cli run --config config/pilot.yaml \
    --provider openai --model gpt-4o-mini \
    --output-dir results/pilot_openai
python3 scripts/validate_run.py --results results/pilot_openai
python3 -m ipd.cli analyze --results results/pilot_openai
```

Notes:
- `config/pilot.yaml` defaults to `provider: mock`. Either pass `--provider` /
  `--model` on the command line (recommended) or edit the `llm:` block.
- Track cost by setting `llm.pricing.*` or passing `--price-in` / `--price-out`
  (USD per 1k tokens). Example for `openai/gpt-4o-mini`:
  `--price-in 0.00015 --price-out 0.0006`. Summarise afterwards with
  `python3 scripts/report_usage.py --results <dir> --price-in 0.00015 --price-out 0.0006`.
- For an OpenAI-compatible endpoint such as OpenRouter, add
  `--base-url https://openrouter.ai/api/v1` and use a model id like
  `openai/gpt-4o-mini`.
- For Anthropic use `--provider anthropic --model <model>` and set
  `ANTHROPIC_API_KEY` (or edit `llm.api_key_env`).
- Any OpenAI-compatible endpoint works: set `llm.base_url` and `llm.api_key_env`.

---

## Running the full experiment (ONLY with explicit approval)

The full configuration is **50 agents per condition × 50 games per agent × both
conditions**. With a real model this is large and potentially expensive. First
run the pilot, estimate cost from `usage_summary.json`, then:

```bash
export OPENAI_API_KEY=sk-...
python3 -m ipd.cli run --config config/full.yaml \
    --provider openai --model <model> \
    --output-dir results/full_openai
python3 scripts/validate_run.py --results results/full_openai
python3 -m ipd.cli analyze --results results/full_openai
```

**The full run is not launched automatically by this repository.**

---

## Configuration reference (`config/*.yaml`)

```yaml
name: pilot                 # experiment name
seed: 20240501              # master random seed (pairing, random horizon)
output_dir: results/pilot
conditions: [fixed, random] # horizons to run
games_per_agent: 2          # number of games each agent plays
fixed_rounds: 20            # rounds per game in the fixed condition
continue_prob: 0.95         # random-horizon continuation probability
max_rounds_random: 200      # safety cap for random-horizon games
pairing_strategy: round_robin   # or "random"

population:
  priors: [0.1, 0.3, 0.5, 0.7, 0.9]
  agents_per_prior: 2       # 2 (pilot) / 10 (full). Total must be even.

llm:
  provider: mock            # mock | openai | anthropic
  model: mock-strategic
  temperature: 0.7
  top_p: 1.0
  max_tokens: 300
  seed: null
  api_key_env: OPENAI_API_KEY
  base_url: null            # for OpenAI-compatible servers
  timeout: 60
  max_retries: 4
  pricing: {input_per_1k_tokens: 0.0, output_per_1k_tokens: 0.0}

memory:
  recent_rounds_in_prompt: 0    # 0 = show every round (lossless)
  max_completed_game_lines: 0   # 0 = show every completed game
```

`python3 -m ipd.cli check --config config/full.yaml` prints the resolved config
and its fingerprint.

---

## Output data

Results are written per condition under `<output_dir>/<condition>/`:

| File | Contents |
|---|---|
| `rounds.jsonl` | one row per agent-round: actions, payoffs, game/lifetime cumulative payoff, parse status, reasoning |
| `games.jsonl` | one row per game: both participants, full round history, totals, end-of-game beliefs, `capped` flag |
| `beliefs.jsonl` | one row per agent-game belief estimate |
| `usage.jsonl` | one row per LLM call: tokens and estimated cost |
| `checkpoint.json` | `next_game_index` for resume, seed and config fingerprint |
| `usage_summary.json` | cumulative token/cost summary |

At the experiment root: `config_snapshot.yaml`, `roster.json`,
`experiment_meta.json`.

Resume with `--resume`: completed game batches are loaded from `games.jsonl`,
each agent's memory is rebuilt, and play continues from the checkpoint. For the
deterministic mock backend a replayed batch reproduces exactly (verified by a
test).

---

## Analysis outputs

`python3 -m ipd.cli analyze --results <dir>` produces `tables/*.csv`,
`figures/*.png` and `report.md`. It computes:

1. **Cooperation rate** per prior group over games (individual trajectories +
   group mean with 95% CI across agents).
2. **Belief evolution** (end-of-game estimate that a new opponent defects).
3. **Average and cumulative payoffs**.
4. **Conditional cooperation** P(cooperate | previous joint outcome CC/CD/DC/DD).
5. **Strategy classification** (AllC, AllD, Tit-for-Tat, Grim Trigger,
   Tit-for-Two-Tats, Mixed/Other) using a transparent prediction-match heuristic;
   when several strategies tie, labels are reported as `Tie: A | B | ...`
   (indistinguishable) rather than forcing one.
6. **Convergence** of final beliefs across prior groups.
7. **Fixed vs random horizon** comparison, including realised game lengths.

Uncertainty is reported as 95% CIs of the mean across agents *within this run*.
Agents interact and are paired repeatedly, so observations are not independent;
the report explicitly avoids significance claims and recommends independent
replications across seeds.

---

## Design notes

- **Pairing.** `round_robin` builds a seeded round-robin schedule with the circle
  method: for `n` agents the first `n-1` games pair every agent with every other
  agent exactly once (randomised labelling), so pairings do not repeat until
  coverage is complete; later games cycle. `random` gives uniform random
  matchings each game.
- **Simultaneity.** In each round both agents' prompts are built and their
  actions obtained *before* either agent's memory is updated; a test asserts the
  round-`r` prompt contains exactly `r-1` observed rounds.
- **Memory (lossless).** Every round of every game is retained in the
  `AgentMemory` object and in `games.jsonl`. The prompt view is lossless: each
  completed game contributes its **full** `you_moves`/`opp_moves` action strings
  (these reconstruct every payoff) plus metadata, and the current game shows all
  rounds by default. `recent_rounds_in_prompt` / `max_completed_game_lines` are
  `0 = unlimited`; if a window is ever set, the full action sequences are still
  included, so no information is lost.
- **Beliefs.** Belief estimates are elicited after each game with a JSON output
  format; no updating formula is imposed.
- **Reproducibility.** Seeds are derived with SHA-256 (`derive_seed`) so pairing
  and random-horizon stopping are stable across processes and resumes.
- **Costs.** Token usage is recorded per call; cost uses the configured prices
  (zero for the mock backend).

---

## Tests

Run `bash scripts/run_tests.sh` (it targets the `ipd/` suite; `tests/` also
contains the dashboard's pytest tests). Coverage includes: payoff matrix;
round-robin/no-repeat/random pairing; exact fixed-horizon length; random-horizon
bounds, cap and reproducibility; simultaneous actions (no look-ahead);
memory isolation, serialisation and **lossless prompt views**; output parsing;
config validation; match record bookkeeping; **strategy tie detection**;
**cost reporting**; and checkpoint/resume (including deterministic replay).

---

## Limitations

- A single run cannot support inferential claims. Repeat across independent seeds
  (and ideally models) for the scientific analysis.
- The strategy classifier is a descriptive heuristic, not a model of the LLM's
  internal computation.
- The offline `mock` backend exists only to test the pipeline; its outputs are
  **not** findings about LLM behaviour.

See `PILOT_REPORT.md` for the status of the pilot and instructions.

---

## Project layout

```
ipd/            core package (game, pairing, memory, prompts, agent, tournament,
                recorder, usage, analysis, cli, llm backends)
config/         smoke / pilot / full configurations
scripts/        validate_run, report_usage, run_tests, dev, check
tests/          unittest suite
results/        generated data, tables, figures, reports (git-ignored)
```

# Part 3 -- OpenRouter swarm-game pilots (`experiments/swarm-game/`)

[The standalone swarm-game runner](experiments/swarm-game/README.md) implements
6-player, 20-round experiments with randomized round-robin matching, private
objectives, simultaneous actions, and either private notes or public communication.
The selfish player maximizes its own cumulative payoff and can cooperate or lie.

[Browse the recorded experiments](experiments/swarm-game/records/README.md):

- **Terra pilot:** 48 episodes comparing none/public communication and zero/one
  selfish player across 12 matched seeds.
- **Luna persona repeat:** 24 public-communication episodes with zero/one selfish
  player; only the selfish player receives the fictional Trump-like persona.

Reports include collective returns, identification, recorded strategy summaries,
messages, exact prompts, frozen runtimes, and losslessly compressed request logs.
The repeat changes both model and persona, so it cannot isolate a personality
effect relative to Terra. Each component retains its own documented game rules.

Install and test this runner from its directory; this command makes no paid
model requests:

```bash
cd experiments/swarm-game
uv sync --locked --no-editable
uv run --no-editable pytest -q
```

The runner's README provides separate launch commands for live experiments.

# intentional-agent

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

# 4. Run the test suite
python3 -m unittest discover -s tests -v      # or: bash scripts/run_tests.sh
```

`scripts/run_experiment.py` and `scripts/analyze.py` are thin wrappers around the
same CLI (`python3 scripts/run_experiment.py --config ...`).

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

Run `python3 -m unittest discover -s tests -v`. Coverage includes: payoff matrix;
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
scripts/        run_experiment, analyze, validate_run, report_usage, run_tests
tests/          unittest suite
results/        generated data, tables, figures, reports (git-ignored)
```



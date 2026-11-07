# Intentional Agent

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

## Recorded OpenRouter pilots

[The standalone swarm-game experiments](experiments/swarm-game/README.md) include
the Python runner, exact prompt templates, tests, and recorded Terra/Luna pilots.
[Browse reports and agent transcripts](experiments/swarm-game/records/README.md).
These experiments retain their documented protocol independently of the dashboard.

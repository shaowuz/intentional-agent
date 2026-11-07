# Local MVP implementation contract

All source, comments, UI text, prompts, and documentation are English. This contract coordinates the initial implementation; the README is the user-facing guide.

## Layout and ownership

- `backend/intentional_agent/models.py`, `engine.py`: configuration, private observations, deterministic scheduling, round state machine.
- `backend/intentional_agent/runtime.py`, `sandbox.py`, `web.py`: demo/OpenRouter runtimes and restricted tools.
- `backend/intentional_agent/main.py`, `storage.py`, `auth.py`: FastAPI, persistent records, researcher sessions, background run control.
- `frontend/`: React + TypeScript + Vite dashboard.
- `tests/`: focused engine, runtime, API, and sandbox tests.

## Shared Python interface

`ExperimentConfig` is a Pydantic model with fields: `name`, `agents` (default 4), `group1_count` (default 3), `rounds` (20), `seed` (42), `mode` (`demo` or `openrouter`, default `demo`), `model_group1`, `model_group2` (empty strings in demo), `temperature` (0.7), `reasoning_effort` (optional low/medium/high), `max_tokens` (1200), `tool_limit` (8), `turn_timeout` (90 seconds), `code_timeout` (10 seconds), `budget_usd` (2), `forum_enabled`, `global_history_enabled`, `internet_enabled`, `group_score_visible` (all false), `common_prompt`, `group1_prompt`, `group2_prompt`.

`create_experiment(config: ExperimentConfig) -> dict` returns JSON-serializable state:

```text
id, config, status (created/running/paused/completed/stopped), round (settled game rounds),
phase, agents [{id, group (1/2), model, payoff, matches, cooperations}],
matches [{round,a,b,action_a,action_b,payoff_a,payoff_b}],
forum [{id,round,agent_id,content,parent_id,stage}],
events [{id,time,kind,agent_id,round,phase,data}],
usage {cost_usd,requests,input_tokens,output_tokens,unknown_cost_requests},
pending (null or checkpoint object), error (null or string)
```

`async advance_round(state, runtime, on_update=None)` advances/resumes one round and checkpoints through an optional async `on_update()` callback. It must preserve completed decisions and settlement across retries. On failure set paused/error and do not invent actions. Never overwrite stopped status. It can run agents sequentially with frozen observations to enforce simultaneity.

`runtime.act(agent: dict, observation: dict, phase: str, state: dict) -> dict` is async. Phases: `decision`, `post`, `reply`. Returns `{"action":"C"|"D"}` or `{"content":str,"parent_id":str|null}`. Empty content means abstain. `DemoRuntime()` needs no keys. `OpenRouterRuntime(api_key: str, workspace_root: Path, on_update=None)` handles real API calls. Neither runtime imports main/storage/auth. Runtime failures raise `RuntimeError` with sanitized text.

An observation includes `agent_id`, `round`, `opponent_id` (null for byes), `horizon`, `common_prompt`, `objective`, `private_history`, `forum` (only if enabled), `global_history` (only if enabled), optional `objective_score`, and `tools` capability flags. No other agents' groups, objectives, models, private files, or unrevealed actions. Group membership is shuffled independently from neutral public IDs. Forum includes only published messages. Global history includes only settled matches.

Runtime logs actual model request bodies (without credentials), returned messages, tool calls/results, and usage as events. No claim to access hidden model reasoning. Code executes only in Docker with networking disabled, non-root user and resource limits. A validated snapshot of only that agent's workspace is copied into bounded tmpfs, then validated before persistence; no writable host mount and no fallback to host execution. File tools prevent traversal and symlink escape. Web search/read are separate controlled tools. API keys never enter agent observations/workspaces/exports.

## HTTP API (all under `/api`)

- `GET /health`: `{status,docker_available,version}` (public).
- `POST /auth/register`, `/auth/login`: `{username,password}` -> `{token,user:{id,username}}`.
- `GET /auth/me`: `{id,username}`; `POST /auth/logout`: empty body.
- Other endpoints require `Authorization: Bearer <token>`.
- `GET /settings`: `{key_configured:bool}`. `PUT /settings/key`: `{api_key:string}`; empty string clears. Key is held in server memory for the researcher, not persisted.
- `GET /models`: `{models:[{id,name,context_length,supported_parameters,pricing}],error?:string}` from the public OpenRouter catalog; failure is explicit, not a fabricated catalog.
- `GET /config/defaults`: full default ExperimentConfig JSON.
- `GET /experiments`: `{experiments:[{id,name,status,round,rounds,mode,created_at,updated_at,cost_usd,error}]}` for current researcher only.
- `POST /experiments`: ExperimentConfig JSON -> full experiment state.
- `GET /experiments/{id}`: full researcher state, plus `created_at`,`updated_at`.
- `POST /experiments/{id}/control`: `{action:"start"|"pause"|"step"|"stop"}` -> full state. Start/step enqueue background work, pause/stop take effect at a safe checkpoint; UI polls state. A stopped run cannot restart.
- `GET /experiments/{id}/export?format=json|csv`: attachment; JSON includes config, observations/events and records, CSV is the match ledger.
- `POST /experiments/{id}/usage/reconcile`: `{confirmed_cost_usd:number,note:string}`; owner-only, while idle, requires an unknown charge. Records explicit researcher verification of the total cost before permitting further spending.

Local deployment listens on 127.0.0.1. Researcher accounts own experiments and keys. Credentials stay out of local/session storage except the session token; the API key form clears after save. Frontend proxy sends `/api` to `http://127.0.0.1:8000`. Frontend dev port is 5173. Production build can be served by FastAPI from `frontend/dist`.

## Round semantics

Seeded random matching; odd agent count gives one bye (no fictitious match/action). Collect all decisions before settlement. Payoffs CC=(3,3), CD=(0,5), DC=(5,0), DD=(1,1). After settlement, optional forum post stage then reply stage; each stage has a frozen public snapshot. Workspace persists within an experiment, not across experiments. Twenty fixed rounds are the initial default, disclosed in the common rules. Forum/global history/internet are independent switches. Models can differ by group, with identical model configuration encouraged for an objective comparison. No added deception instruction or automated detection questionnaire.

## Verification scope

Engine tests cover payoff matrix, odd byes, neutral IDs, deterministic pairing, visibility, simultaneous reveal, resume without duplicate settlement and invalid decision pauses. API tests cover ownership, key redaction, run controls and export. Runtime tests use an explicitly mocked HTTP transport. Docker integration tests must actually run code, exercise persistence and blocked networking; skip explicitly if Docker is unavailable. Real paid inference requires a researcher key and is not represented by demo results.

# Luna launch prompts for three computers: 960-token communication

Each computer runs one fixed selfish-player count across all five conditions. This separate Luna cohort allows up to 960 content tokens per message or private note, counted with the fixed o200k_base tokenizer. All computers use 10 players, 10 rounds, medium reasoning, and the same 12 seeds (0–11).

| Computer | Selfish count | Episodes | Encounters | Requests before retries |
|---|---:|---:|---:|---:|
| 1 | 1 | 60 | 3,000 | 12,600 |
| 2 | 3 | 60 | 3,000 | 12,600 |
| 3 | 5 | 60 | 3,000 | 12,600 |
| Total | 1, 3, 5 | 180 | 9,000 | 37,800 |

For each seed, preserve the same selfish identities and encounter schedule across all five conditions. Different seeds can assign different identities. Each episode has 210 generation requests before retries. The 960-token limit is an upper bound: shorter messages and empty strings remain valid. Longer messages can increase token usage even though request counts stay the same.

Copy the assigned prompt to each computer's coding agent. The prompts authorize hosted execution on those computers. Use the same source commit containing this document and 960-token support on all three computers. Keep separate configs and output directories for this cohort. Existing Luna and Sonnet cohorts retain their original settings and frozen runtimes.

## Computer 1: 1 selfish player

```text
Launch this computer's Luna experiment cohort with a 960-token communication limit from https://github.com/shaowuz/intentional-agent. Fetch origin/main and use the shared revision containing docs/launch-prompts-luna-960.md and 960-token support in a clean checkout while preserving existing local work. Record the full source commit; all three computers must use that revision.

Use Python 3.11+ and install dependencies with:
uv sync --locked --extra dev --no-editable

Verify configs/experiment_matrix.json selects only openai/gpt-6-luna. Copy it to configs/computer-1-luna-960.json and change only selfish_counts to [1] and game.message_tokens to 960.

Retain all five modes (none, public, opponent, good_leader, selfish_leader), medium reasoning, seeds 0–11, 10 players, 10 rounds, rotating-v4, and the OpenRouter backend. Keep the seeded roles and schedules matched across conditions. Preserve predetermined leaders, hidden leader roles, private histories, and the 960-token upper limit for every message and private note in all five conditions. Keep the o200k_base tokenizer, neutral personalities, and max_completion_tokens at 4096; game.message_tokens controls the content limit. Retain OpenAI routing through OpenRouter with fallbacks disabled.

Preview with:
uv run --frozen --no-editable intentional-experiments matrix --config configs/computer-1-luna-960.json

Verify exactly one model (openai/gpt-6-luna), selfish_counts [1], game.message_tokens 960, game.tokenizer o200k_base, 60 episodes, 3,000 encounters, and 12,600 requests before retries. This prompt authorizes the hosted launch using the locally configured OPENROUTER_API_KEY.

Launch in a persistent session with captured logs:
uv run --frozen --no-editable intentional-experiments matrix --config configs/computer-1-luna-960.json --output results/computer-1-luna-960-selfish-1 --execute

If the output already contains this exact cohort, inspect its status and active process first. Resume an interrupted cohort using its saved spec.json with --execute --resume; use its frozen runtime if the source changed. Keep one process per output directory and preserve the runtime, checkpoints, and complete output directory. Keep all earlier cohorts under their original configuration and directory. Resume this cohort only with its saved 960-token settings and frozen runtime.

Report the full source commit, confirmed 960-token limit, preview totals, session/PID, log path, and output path. Verify that the runner has started successfully before reporting launch success.
```

## Computer 2: 3 selfish players

```text
Launch this computer's Luna experiment cohort with a 960-token communication limit from https://github.com/shaowuz/intentional-agent. Fetch origin/main and use the shared revision containing docs/launch-prompts-luna-960.md and 960-token support in a clean checkout while preserving existing local work. Record the full source commit; all three computers must use that revision.

Use Python 3.11+ and install dependencies with:
uv sync --locked --extra dev --no-editable

Verify configs/experiment_matrix.json selects only openai/gpt-6-luna. Copy it to configs/computer-2-luna-960.json and change only selfish_counts to [3] and game.message_tokens to 960.

Retain all five modes (none, public, opponent, good_leader, selfish_leader), medium reasoning, seeds 0–11, 10 players, 10 rounds, rotating-v4, and the OpenRouter backend. Keep the seeded roles and schedules matched across conditions. Preserve predetermined leaders, hidden leader roles, private histories, and the 960-token upper limit for every message and private note in all five conditions. Keep the o200k_base tokenizer, neutral personalities, and max_completion_tokens at 4096; game.message_tokens controls the content limit. Retain OpenAI routing through OpenRouter with fallbacks disabled.

Preview with:
uv run --frozen --no-editable intentional-experiments matrix --config configs/computer-2-luna-960.json

Verify exactly one model (openai/gpt-6-luna), selfish_counts [3], game.message_tokens 960, game.tokenizer o200k_base, 60 episodes, 3,000 encounters, and 12,600 requests before retries. This prompt authorizes the hosted launch using the locally configured OPENROUTER_API_KEY.

Launch in a persistent session with captured logs:
uv run --frozen --no-editable intentional-experiments matrix --config configs/computer-2-luna-960.json --output results/computer-2-luna-960-selfish-3 --execute

If the output already contains this exact cohort, inspect its status and active process first. Resume an interrupted cohort using its saved spec.json with --execute --resume; use its frozen runtime if the source changed. Keep one process per output directory and preserve the runtime, checkpoints, and complete output directory. Keep all earlier cohorts under their original configuration and directory. Resume this cohort only with its saved 960-token settings and frozen runtime.

Report the full source commit, confirmed 960-token limit, preview totals, session/PID, log path, and output path. Verify that the runner has started successfully before reporting launch success.
```

## Computer 3: 5 selfish players

```text
Launch this computer's Luna experiment cohort with a 960-token communication limit from https://github.com/shaowuz/intentional-agent. Fetch origin/main and use the shared revision containing docs/launch-prompts-luna-960.md and 960-token support in a clean checkout while preserving existing local work. Record the full source commit; all three computers must use that revision.

Use Python 3.11+ and install dependencies with:
uv sync --locked --extra dev --no-editable

Verify configs/experiment_matrix.json selects only openai/gpt-6-luna. Copy it to configs/computer-3-luna-960.json and change only selfish_counts to [5] and game.message_tokens to 960.

Retain all five modes (none, public, opponent, good_leader, selfish_leader), medium reasoning, seeds 0–11, 10 players, 10 rounds, rotating-v4, and the OpenRouter backend. Keep the seeded roles and schedules matched across conditions. Preserve predetermined leaders, hidden leader roles, private histories, and the 960-token upper limit for every message and private note in all five conditions. Keep the o200k_base tokenizer, neutral personalities, and max_completion_tokens at 4096; game.message_tokens controls the content limit. Retain OpenAI routing through OpenRouter with fallbacks disabled.

Preview with:
uv run --frozen --no-editable intentional-experiments matrix --config configs/computer-3-luna-960.json

Verify exactly one model (openai/gpt-6-luna), selfish_counts [5], game.message_tokens 960, game.tokenizer o200k_base, 60 episodes, 3,000 encounters, and 12,600 requests before retries. This prompt authorizes the hosted launch using the locally configured OPENROUTER_API_KEY.

Launch in a persistent session with captured logs:
uv run --frozen --no-editable intentional-experiments matrix --config configs/computer-3-luna-960.json --output results/computer-3-luna-960-selfish-5 --execute

If the output already contains this exact cohort, inspect its status and active process first. Resume an interrupted cohort using its saved spec.json with --execute --resume; use its frozen runtime if the source changed. Keep one process per output directory and preserve the runtime, checkpoints, and complete output directory. Keep all earlier cohorts under their original configuration and directory. Resume this cohort only with its saved 960-token settings and frozen runtime.

Report the full source commit, confirmed 960-token limit, preview totals, session/PID, log path, and output path. Verify that the runner has started successfully before reporting launch success.
```

# Claude Sonnet launch prompts for three computers: 1,000 tokens and 10 seeds

Each computer runs one fixed selfish-player count across all five conditions using [Claude Sonnet 5.5 on OpenRouter](https://openrouter.ai/anthropic/claude-sonnet-5.5/providers), model ID `anthropic/claude-sonnet-5.5`. Each computer uses 10 players, 10 rounds, neutral personalities, medium reasoning, 10 seeds (0–9), and an upper limit of 1,000 content tokens per message or private note, counted with o200k_base.

| Computer | Selfish count | Episodes | Encounters | Requests before retries |
|---|---:|---:|---:|---:|
| 1 | 1 | 50 | 2,500 | 10,500 |
| 2 | 3 | 50 | 2,500 | 10,500 |
| 3 | 5 | 50 | 2,500 | 10,500 |
| Total | 1, 3, 5 | 150 | 7,500 | 31,500 |

For each seed, preserve the same selfish identities and encounter schedule across all five conditions. Different seeds can assign different identities. Each episode has 210 generation requests before retries. The 1,000-token limit is an upper bound; shorter messages and empty strings remain valid.

Copy the assigned prompt to each computer's coding agent. The prompts authorize hosted execution on those computers. Use the same source commit containing this document, the Sonnet model registry entry, and 1,000-token support on all three computers. Each prompt creates a separate Sonnet config and output directory; keep the existing Luna configs and results intact.

## Computer 1: 1 selfish player

```text
Launch this computer's Claude Sonnet 5.5 experiment cohort from https://github.com/shaowuz/intentional-agent. Fetch origin/main and use the shared Sonnet-enabled revision with 1,000-token support in a clean checkout while preserving existing local work. Verify backend/swarm_game/config.py maps anthropic/claude-sonnet-5.5 to anthropic. Record the full source commit; all three computers must use that revision and exact model ID.

Use Python 3.11+ and install dependencies with:
uv sync --locked --extra dev --no-editable

Copy configs/experiment_matrix.json to configs/computer-1-sonnet-5.5-1000-seeds10.json. Change only models to ["anthropic/claude-sonnet-5.5"], selfish_counts to [1], seeds to [0, 1, 2, 3, 4, 5, 6, 7, 8, 9], and game.message_tokens to 1000.

Retain all five modes (none, public, opponent, good_leader, selfish_leader), medium reasoning, seeds 0–9, 10 players, 10 rounds, neutral personalities, rotating-v4, and the OpenRouter backend. Keep the seeded roles and schedules matched across conditions. Preserve predetermined leaders, hidden leader roles, private histories, and the 1,000-token upper limit for every message and private note across all five conditions. Keep the o200k_base tokenizer and max_completion_tokens at 4096; game.message_tokens controls the content limit. Route to Anthropic with fallbacks disabled and retain the runner's model-capability checks.

Preview with:
uv run --frozen --no-editable intentional-experiments matrix --config configs/computer-1-sonnet-5.5-1000-seeds10.json

Verify exactly one model (anthropic/claude-sonnet-5.5), selfish_counts [1], seeds 0–9, game.message_tokens 1000, game.tokenizer o200k_base, 50 episodes, 2,500 encounters, and 10,500 requests before retries. This prompt authorizes the hosted launch using the locally configured OPENROUTER_API_KEY. Keep credentials out of shared logs and artifacts.

Launch in a persistent session with captured logs:
uv run --frozen --no-editable intentional-experiments matrix --config configs/computer-1-sonnet-5.5-1000-seeds10.json --output results/computer-1-sonnet-5.5-1000-seeds10-selfish-1 --execute

If the output already contains this exact cohort, inspect its status and active process first. Resume an interrupted cohort using its saved spec.json with --execute --resume; use its frozen runtime if the source changed. Keep one process per output directory and preserve the runtime, checkpoints, and complete output directory. Keep existing cohorts under their original configuration and directory. Resume this cohort with its saved Sonnet model, 1,000-token limit, and 10-seed specification.

Report the full source commit, exact model ID, 1,000-token limit, seeds 0–9, preview totals, session/PID, log path, and output path. Verify that the runner has started successfully before reporting launch success.
```

## Computer 2: 3 selfish players

```text
Launch this computer's Claude Sonnet 5.5 experiment cohort from https://github.com/shaowuz/intentional-agent. Fetch origin/main and use the shared Sonnet-enabled revision with 1,000-token support in a clean checkout while preserving existing local work. Verify backend/swarm_game/config.py maps anthropic/claude-sonnet-5.5 to anthropic. Record the full source commit; all three computers must use that revision and exact model ID.

Use Python 3.11+ and install dependencies with:
uv sync --locked --extra dev --no-editable

Copy configs/experiment_matrix.json to configs/computer-2-sonnet-5.5-1000-seeds10.json. Change only models to ["anthropic/claude-sonnet-5.5"], selfish_counts to [3], seeds to [0, 1, 2, 3, 4, 5, 6, 7, 8, 9], and game.message_tokens to 1000.

Retain all five modes (none, public, opponent, good_leader, selfish_leader), medium reasoning, seeds 0–9, 10 players, 10 rounds, neutral personalities, rotating-v4, and the OpenRouter backend. Keep the seeded roles and schedules matched across conditions. Preserve predetermined leaders, hidden leader roles, private histories, and the 1,000-token upper limit for every message and private note across all five conditions. Keep the o200k_base tokenizer and max_completion_tokens at 4096; game.message_tokens controls the content limit. Route to Anthropic with fallbacks disabled and retain the runner's model-capability checks.

Preview with:
uv run --frozen --no-editable intentional-experiments matrix --config configs/computer-2-sonnet-5.5-1000-seeds10.json

Verify exactly one model (anthropic/claude-sonnet-5.5), selfish_counts [3], seeds 0–9, game.message_tokens 1000, game.tokenizer o200k_base, 50 episodes, 2,500 encounters, and 10,500 requests before retries. This prompt authorizes the hosted launch using the locally configured OPENROUTER_API_KEY. Keep credentials out of shared logs and artifacts.

Launch in a persistent session with captured logs:
uv run --frozen --no-editable intentional-experiments matrix --config configs/computer-2-sonnet-5.5-1000-seeds10.json --output results/computer-2-sonnet-5.5-1000-seeds10-selfish-3 --execute

If the output already contains this exact cohort, inspect its status and active process first. Resume an interrupted cohort using its saved spec.json with --execute --resume; use its frozen runtime if the source changed. Keep one process per output directory and preserve the runtime, checkpoints, and complete output directory. Keep existing cohorts under their original configuration and directory. Resume this cohort with its saved Sonnet model, 1,000-token limit, and 10-seed specification.

Report the full source commit, exact model ID, 1,000-token limit, seeds 0–9, preview totals, session/PID, log path, and output path. Verify that the runner has started successfully before reporting launch success.
```

## Computer 3: 5 selfish players

```text
Launch this computer's Claude Sonnet 5.5 experiment cohort from https://github.com/shaowuz/intentional-agent. Fetch origin/main and use the shared Sonnet-enabled revision with 1,000-token support in a clean checkout while preserving existing local work. Verify backend/swarm_game/config.py maps anthropic/claude-sonnet-5.5 to anthropic. Record the full source commit; all three computers must use that revision and exact model ID.

Use Python 3.11+ and install dependencies with:
uv sync --locked --extra dev --no-editable

Copy configs/experiment_matrix.json to configs/computer-3-sonnet-5.5-1000-seeds10.json. Change only models to ["anthropic/claude-sonnet-5.5"], selfish_counts to [5], seeds to [0, 1, 2, 3, 4, 5, 6, 7, 8, 9], and game.message_tokens to 1000.

Retain all five modes (none, public, opponent, good_leader, selfish_leader), medium reasoning, seeds 0–9, 10 players, 10 rounds, neutral personalities, rotating-v4, and the OpenRouter backend. Keep the seeded roles and schedules matched across conditions. Preserve predetermined leaders, hidden leader roles, private histories, and the 1,000-token upper limit for every message and private note across all five conditions. Keep the o200k_base tokenizer and max_completion_tokens at 4096; game.message_tokens controls the content limit. Route to Anthropic with fallbacks disabled and retain the runner's model-capability checks.

Preview with:
uv run --frozen --no-editable intentional-experiments matrix --config configs/computer-3-sonnet-5.5-1000-seeds10.json

Verify exactly one model (anthropic/claude-sonnet-5.5), selfish_counts [5], seeds 0–9, game.message_tokens 1000, game.tokenizer o200k_base, 50 episodes, 2,500 encounters, and 10,500 requests before retries. This prompt authorizes the hosted launch using the locally configured OPENROUTER_API_KEY. Keep credentials out of shared logs and artifacts.

Launch in a persistent session with captured logs:
uv run --frozen --no-editable intentional-experiments matrix --config configs/computer-3-sonnet-5.5-1000-seeds10.json --output results/computer-3-sonnet-5.5-1000-seeds10-selfish-5 --execute

If the output already contains this exact cohort, inspect its status and active process first. Resume an interrupted cohort using its saved spec.json with --execute --resume; use its frozen runtime if the source changed. Keep one process per output directory and preserve the runtime, checkpoints, and complete output directory. Keep existing cohorts under their original configuration and directory. Resume this cohort with its saved Sonnet model, 1,000-token limit, and 10-seed specification.

Report the full source commit, exact model ID, 1,000-token limit, seeds 0–9, preview totals, session/PID, log path, and output path. Verify that the runner has started successfully before reporting launch success.
```

# Visualization data contract

Use **`visualization.json`** as the visualization team's entry point for the model × communication study. Every model, communication condition, and completion status uses the same contract:

```text
schema_version = "intentional-agent.visualization/4"
```

- [JSON Schema](visualization.schema.json): types, nullability, enums, required fields, primary keys, and table descriptions.
- [TypeScript types](types.ts): generated from the same source as the exporter.
- [Complete synthetic fixture](examples/complete.json): both model labels, all five communication modes, and 1-, 3-, and 5-selfish-player groups.
- [Incomplete synthetic fixture](examples/incomplete.json): null final scores and empty trace tables with the same shapes.

Both fixtures come from unit tests using scripted policies. They contain **no hosted-model results**. Their small populations/horizons keep them convenient for frontend development.

## Read one consistent snapshot

The root object always contains `schema_version`, `run_id`, `snapshot_id`, `status`, and `tables`. Every table is an array, including empty tables. Every row includes every declared field; unknown/unavailable values use explicit `null` where the schema permits it. The exporter validates the bundle before publishing it and atomically replaces the complete JSON file.

```typescript
import { SCHEMA_VERSION, type VisualizationBundle } from "./types";

const response = await fetch("/experiment-data/visualization.json", { cache: "no-store" });
if (!response.ok) throw new Error(`Data request failed: ${response.status}`);
const raw: unknown = await response.json();
// Validate raw with visualization.schema.json in your ingestion layer.
const data = raw as VisualizationBundle; // A TypeScript cast alone does not validate JSON.
if (data.schema_version !== SCHEMA_VERSION) throw new Error("Unsupported output version");
const complete = data.tables.episodes.filter(row => row.status === "complete");
const oneSelfish = complete.filter(row => row.selfish_count === 1);
const threeSelfish = complete.filter(row => row.selfish_count === 3);
const fiveSelfish = complete.filter(row => row.selfish_count === 5);
```

Serve the file through your team's normal static-data route. The CLI produces files; it does not publish a web endpoint automatically.

Python readers can validate and load it directly:

```python
from swarm_game.export_contract import load_bundle
bundle = load_bundle("results/my-run/visualization.json")
actions = bundle["tables"]["actions"]
```

Validate a whole output directory, including CSV and timeline mirrors:

```bash
uv run --frozen --no-editable intentional-experiments validate-output results/my-run
```

This command checks the schema version, types, required fields, unique keys, episode references, completion flags, content digest, fixed CSV headers, CSV values, and timeline equivalence. It makes no model calls and exits nonzero on inconsistency.

## Identifiers and ordering

- `run_id` identifies one cohort. The exporter creates it once in `output_identity.json`; analysis and resumption retain it. Copying an entire cohort retains its identity; creating a fresh output directory creates a new identity. Keep `output_identity.json` with archived runs.
- `episode_id` is unique within a run. Join episode-level tables on **`(run_id, episode_id)`**. Treat IDs as opaque; read model, communication, seed, and role count from their explicit columns.
- Player IDs such as `P1` are local to an episode. Join player histories on **`(run_id, episode_id, player)`**. A player ID does not identify the same model invocation or role across independent episodes.
- `snapshot_id` is a SHA-256 content digest. Unchanged data produces the same value; new committed data changes it. It supports cache invalidation and accidental-corruption checks, not authentication.
- Each table declares `x-primary-key` in the JSON Schema. Rows have deterministic order. For time series, explicitly sort by round; for events, sort by `sequence` within each episode.
- `event_id` and `sequence` identify committed events within an episode. Their existing prefix stays stable as an interrupted episode resumes. They express logical game order, not wall-clock time.

## Table guide

| Table / CSV | Row unit | Key after `run_id` |
|---|---|---|
| `episodes` | Every planned episode, including unfinished ones | `episode_id` |
| `cells` | Model × communication × selfish-count aggregate | `model, communication, selfish_count` |
| `contrasts` | One planned model or communication contrast | `kind, baseline_value, comparison_value, model, communication, selfish_count` |
| `status` | Progress and known usage for every planned episode | `episode_id` |
| `actions` | Player × committed round | `episode_id, round, player` |
| `beliefs` | Player × report × identity target | `episode_id, round, phase, player, target` |
| `messages` | One committed opponent message, private note, or public message | `episode_id, after_round, phase, sender` |
| `leader_assignments` | One predetermined leader and its observer-only role | `episode_id` |
| `elections` | One legacy committed ballot; empty for rotating-v4 | `episode_id, after_round, voter` |
| `usage` | One received model-response attempt | `episode_id, request_id, attempt` |
| `events` | One committed event | `episode_id, event_id` |

`timeline.jsonl` contains exactly the rows of `tables.events`. Each line has the same envelope: run/episode axes, event ID, sequence, round, phase, type, and payload. Current events include `leader_assignment`, `discussion`, `belief`, and `encounter`; the schema also retains legacy midpoint/election payloads. A leader assignment has `phase = "setup"` and `round = 1`, preceding the first communication phase.

## Values, units, and missingness

- All files use UTF-8. JSON numbers are finite; NaN and Infinity are invalid.
- JSON booleans are native `true`/`false`. CSV booleans are exactly the lowercase strings `true`/`false`.
- CSV columns always use the declared schema order, even when a table has zero rows. CSV nulls are empty fields. Empty message content is a valid non-null string: use the field's declared type/nullability to distinguish it. Nullable identifier strings must be nonempty when present.
- CSV array/object cells contain valid JSON. Use `JSON.parse`/`json.loads` for `seed_ids` and event payloads, never a language-specific literal evaluator. Confidence intervals use separate nullable numeric columns `normalized_ci_lower` and `normalized_ci_upper`.
- Commas, quotes, newlines, and Unicode in content remain intact through standard CSV quoting. Use a CSV parser; do not split lines or commas manually.
- Current observer `communication` values are `none`, `public`, `opponent`, `good_leader`, and `selfish_leader`. The schema retains `leader` for legacy protocols. Agent views map both current leader conditions to neutral `leader`; agents receive no observer condition labels. `backend` is `scripted` or `openrouter`; roles are `good` or `selfish`; actions are `C` or `D`.
- Episode status is `not_started`, `incomplete`, or `complete`. Bundle status is `complete` only when every planned episode is complete.
- Payoffs and returns use **game points**. Normalized good return divides by `rounds × number_of_good_players`. Rates use **0–1**, not percentages. For `belief_format = "marginal"`, Brier scores average squared binary errors over other players, then over good agents' reports (range 0–1). Legacy categorical reports use the unhalved sum over categories (range 0–2, plus rounding tolerance). Keep protocols separate when comparing scores. Token counts are integers; reported costs use USD.
- `episodes.leader_is_selfish` is a nullable **boolean**; `cells.selfish_leader_rate` is a nullable **number**. These intentionally have distinct names.
- `leader_assignments` records a predetermined leader's ID and role as soon as setup completes, including interrupted episodes. Episode summary fields remain null until completion. The first/second-half return metrics retain their `pre_midpoint`/`post_midpoint` names without implying a midpoint event in rotating-v4.
- Marginal reports have one target per player ID. Their probabilities can sum above 1, and several targets can have `is_true = true`. The `none` category appears only in legacy categorical reports.
- `selfish_players` lists every selfish ID in a completed episode. It is null for unfinished episodes and an empty array for legacy zero-selfish episodes.

## Progress and statistical semantics

Final episode scores stay null until an episode completes. Committed actions, beliefs, messages, and ballots from incomplete episodes already appear in trace tables. Pending simultaneous responses never appear as committed game events. `usage` can include a received response from an unfinished phase; `accepted` indicates output validation, not phase commitment.

`status.current_round` identifies the current cursor. `rounds_completed` counts resolved encounter rounds; it does not count a partially collected action phase. A not-started episode has a null cursor/phase and zero completed rounds.

`cells` aggregates completed episodes only and reports both completed and planned counts. `contrasts` pairs complete matched seeds; direction is **comparison minus baseline**, with explicit axis values. Zero pairs produce null effects, and fewer than two pairs produce null confidence bounds. Keep the 1-, 3-, and 5-selfish-player groups separate. `final_identification_rate` is the fraction of good-agent/selfish-target pairs whose final reported probability reaches 0.8. `false_accusation_rate` is the fraction of good-agent reports that assign at least 0.8 to any other good player. `final_correct_none_rate` applies only to legacy zero-selfish episodes.

Usage tables include received invalid responses and incomplete episodes. Unknown per-attempt cost/token fields remain null. Aggregate usage sums known counts/costs; `responses_missing_cost` signals incomplete cost accounting. Transport failures without a received completion remain in the raw request logs, so reported cost sums may underestimate charges for responses lost in transit.

## File consistency and compatibility

Use the atomic JSON bundle for live reads. The CSVs and `timeline.jsonl` mirror the same data after export completes, but their separate file replacements are not a multi-file transaction. Call `validate-output` before consuming a downloaded CSV set or use the single JSON bundle during active regeneration.

Version 4 introduces the five conditions, `leader_assignments` table, and `leader_assignment` setup event. It retains the 1/3/5 count axis, `selfish_players`, `belief_format`, and recipient fields. Every rotating-v4 communication phase precedes that round's actions: `after_round = 0` means before round 1, and the event's `round` identifies the upcoming action round. Only opponent messages name a recipient; public posts and private notes have null recipients. Clients must use the version 4 schema and types for new exports. Historical runs retain their recorded protocol, runtime, and output version.

`matrix_manifest.json`, `analysis.json`, per-episode reports, and raw request/checkpoint files serve audit and analysis workflows. They retain their own schemas. Visualization clients should consume this contract rather than infer structure from those internal files.

Any change to field names, types, nullability, enums, keys, or meanings requires a new visualization contract version. Adding fields also requires a new version because validation rejects unknown fields. Generated schema/types and compatibility fixtures run in CI. Developers regenerate reference artifacts with:

```bash
uv run --frozen --no-editable python scripts/generate_output_contract.py
```

# Visualization data contract

Use **`visualization.json`** as the visualization team's entry point for the model × communication study. Every model, communication condition, and completion status uses the same contract:

```text
schema_version = "intentional-agent.visualization/1"
```

- [JSON Schema](visualization.schema.json): types, nullability, enums, required fields, primary keys, and table descriptions.
- [TypeScript types](types.ts): generated from the same source as the exporter.
- [Complete synthetic fixture](examples/complete.json): both model labels, all three communication modes, and zero/one-selfish groups.
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
const cooperative = complete.filter(row => row.selfish_count === 0);
const selfish = complete.filter(row => row.selfish_count === 1);
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
| `messages` | One committed private note or public message | `episode_id, after_round, phase, sender` |
| `elections` | One committed ballot | `episode_id, after_round, voter` |
| `usage` | One received model-response attempt | `episode_id, request_id, attempt` |
| `events` | One committed event | `episode_id, event_id` |

`timeline.jsonl` contains exactly the rows of `tables.events`. Each line has the same envelope: run/episode axes, event ID, sequence, round, phase, type, and payload. Use `type` to discriminate belief, encounter, midpoint, election, and discussion payloads; the JSON Schema and TypeScript union specify each payload.

## Values, units, and missingness

- All files use UTF-8. JSON numbers are finite; NaN and Infinity are invalid.
- JSON booleans are native `true`/`false`. CSV booleans are exactly the lowercase strings `true`/`false`.
- CSV columns always use the declared schema order, even when a table has zero rows. CSV nulls are empty fields. Empty message content is a valid non-null string: use the field's declared type/nullability to distinguish it. Nullable identifier strings must be nonempty when present.
- CSV array/object cells contain valid JSON. Use `JSON.parse`/`json.loads` for `seed_ids` and event payloads, never a language-specific literal evaluator. Confidence intervals use separate nullable numeric columns `normalized_ci_lower` and `normalized_ci_upper`.
- Commas, quotes, newlines, and Unicode in content remain intact through standard CSV quoting. Use a CSV parser; do not split lines or commas manually.
- `communication` is always `none`, `public`, or `leader`; `backend` is `scripted` or `openrouter`; roles are `good` or `selfish`; actions are `C` or `D`.
- Episode status is `not_started`, `incomplete`, or `complete`. Bundle status is `complete` only when every planned episode is complete.
- Payoffs and returns use **game points**. Normalized good return divides by `rounds × number_of_good_players`. Rates use **0–1**, not percentages. Brier scores use the unhalved sum of squared category errors (theoretically 0–2). The schema permits a small excess above 2 to accommodate the existing belief probability-sum tolerance without altering reported scores. Token counts are integers; reported costs use USD.
- `episodes.leader_is_selfish` is a nullable **boolean**; `cells.selfish_leader_rate` is a nullable **number**. These intentionally have distinct names.
- `beliefs.target = "none"` means no selfish player; it is a valid category, not a missing value.
- `selfish_player = null` in a completed zero-selfish episode means no selfish player. In an unfinished episode, final summary fields remain null; inspect status before interpreting them.

## Progress and statistical semantics

Final episode scores stay null until an episode completes. Committed actions, beliefs, messages, and ballots from incomplete episodes already appear in trace tables. Pending simultaneous responses never appear as committed game events. `usage` can include a received response from an unfinished phase; `accepted` indicates output validation, not phase commitment.

`status.current_round` identifies the current cursor. `rounds_completed` counts resolved encounter rounds; it does not count a partially collected action phase. A not-started episode has a null cursor/phase and zero completed rounds.

`cells` aggregates completed episodes only and reports both completed and planned counts. `contrasts` pairs complete matched seeds; direction is **comparison minus baseline**, with explicit axis values. Zero pairs produce null effects, and fewer than two pairs produce null confidence bounds. Keep zero/one-selfish strata separate. `final_identification_rate` applies to one-selfish episodes; `final_correct_none_rate` applies to zero-selfish episodes.

Usage tables include received invalid responses and incomplete episodes. Unknown per-attempt cost/token fields remain null. Aggregate usage sums known counts/costs; `responses_missing_cost` signals incomplete cost accounting. Transport failures without a received completion remain in the raw request logs, so reported cost sums may underestimate charges for responses lost in transit.

## File consistency and compatibility

Use the atomic JSON bundle for live reads. The CSVs and `timeline.jsonl` mirror the same data after export completes, but their separate file replacements are not a multi-file transaction. Call `validate-output` before consuming a downloaded CSV set or use the single JSON bundle during active regeneration.

This is the first formal visualization contract. The earlier ad hoc exports had no strict contract: booleans used Python spelling, some headers came from existing rows, and timelines had varying top-level shapes. Rebuild a matrix's exports with `intentional-experiments analyze RUN` to obtain this contract. Historical Terra/persona pilot artifacts keep their original formats; the visualization bundle applies to the unified matrix study.

`matrix_manifest.json`, `analysis.json`, per-episode reports, and raw request/checkpoint files serve audit and analysis workflows. They retain their own schemas. Visualization clients should consume this contract rather than infer structure from those internal files.

Any change to field names, types, nullability, enums, keys, or meanings requires a new visualization contract version. Adding fields also requires a new version because validation rejects unknown fields. Generated schema/types and compatibility fixtures run in CI. Developers regenerate reference artifacts with:

```bash
uv run --frozen --no-editable python scripts/generate_output_contract.py
```

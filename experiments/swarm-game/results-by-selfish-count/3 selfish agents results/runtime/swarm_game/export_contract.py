"""Versioned, typed observer exports consumed by visualization clients.

The JSON bundle is the atomic source of truth. CSV and JSONL mirror its tables.
Keep field order, null conventions, and identifiers stable within this version.
"""

import csv
import hashlib
import io
import json
import os
import tempfile
from pathlib import Path
from uuid import uuid4

import jsonschema

from .config import COMMUNICATION_MODES
from .storage import exclusive_run, read_json, scrub, write_json

VERSION = "intentional-agent.visualization/4"


def field(kind, *, nullable=False, enum=None, description="", **extra):
    value = {"type": [kind, "null"] if nullable else kind, **extra}
    if enum is not None:
        value["enum"] = [*enum, None] if nullable else list(enum)
    if description:
        value["description"] = description
    return value


S = field("string", minLength=1)
TEXT = field("string")
NS = field("string", nullable=True, minLength=1)
I = field("integer", minimum=0)
R = field("integer", minimum=1)
N = field("number", nullable=True)
RATE = field("number", nullable=True, minimum=0, maximum=1)
BOOL = field("boolean")
MODE = field("string", enum=[*COMMUNICATION_MODES, "leader"])
ROLE = field("string", enum=["good", "selfish"])
STATUS = field("string", enum=["not_started", "incomplete", "complete"])
PHASE = field("string", enum=["setup", "pre_round", "action", "midpoint", "discussion", "final"])
RUN = {"run_id": field("string", format="uuid")}
AXES = {
    **RUN,
    "episode_id": S,
    "model": S,
    "communication": MODE,
    "selfish_count": field("integer", enum=[0, 1, 3, 5]),
    "seed": I,
    "backend": field("string", enum=["openrouter", "scripted"]),
}
USAGE_TOTALS = {
    "completed_model_responses": I,
    "prompt_tokens": I,
    "completion_tokens": I,
    "reported_cost_usd": field(
        "number", minimum=0, description="Sum of known reported costs in USD; may be incomplete."
    ),
    "responses_missing_cost": I,
}
METRICS = {
    "good_total_return": field(
        "integer",
        nullable=True,
        minimum=0,
        description="Total payoff points of all actual good players; null until complete.",
    ),
    "return_per_good_encounter": field(
        "number",
        nullable=True,
        minimum=0,
        maximum=5,
        description="Good total return / (rounds × number of good players).",
    ),
    "good_good_return": field("integer", nullable=True, minimum=0),
    "good_selfish_return": field("integer", nullable=True, minimum=0),
    "good_cooperation_rate": RATE,
    "all_cooperation_rate": RATE,
    "mean_brier_score": field(
        "number", nullable=True, minimum=0, maximum=2.000002,
        description="Marginal: mean binary error over other players, then good-agent reports. Legacy categorical: summed category error.",
    ),
    "final_mean_brier_score": field(
        "number", nullable=True, minimum=0, maximum=2.000002,
        description="Same Brier definition using final good-agent reports only.",
    ),
    "final_identification_rate": field(
        "number", nullable=True, minimum=0, maximum=1,
        description="Fraction of good-agent/selfish-target pairs with final probability >= 0.8; null with no selfish players.",
    ),
    "final_correct_none_rate": RATE,
    "false_accusation_rate": RATE,
    "leader_is_selfish": field(
        "boolean",
        nullable=True,
        description="True/false for a predetermined or legacy elected leader; null if no leader or episode incomplete.",
    ),
    "pre_midpoint_return_per_good_encounter": field("number", nullable=True, minimum=0, maximum=5),
    "post_midpoint_return_per_good_encounter": field("number", nullable=True, minimum=0, maximum=5),
}
CELL_METRICS = {
    ("selfish_leader_rate" if k == "leader_is_selfish" else k): (
        RATE if k == "leader_is_selfish" else {**v, "type": ["number", "null"]}
    )
    for k, v in METRICS.items()
}


def table(properties, key, grain):
    return {
        "type": "object",
        "properties": properties,
        "required": list(properties),
        "additionalProperties": False,
        "x-primary-key": ["run_id", *key],
        "description": grain,
    }


TABLES = {
    "episodes": table(
        {
            **AXES,
            "status": STATUS,
            "protocol_version": S,
            "belief_format": field("string", enum=["categorical", "marginal"]),
            "players": R,
            "rounds": R,
            "reasoning_effort": S,
            "selfish_persona": S,
            **METRICS,
            "leader": NS,
            "selfish_players": field("array", nullable=True, items=S, uniqueItems=True),
            **USAGE_TOTALS,
        },
        ["episode_id"],
        "One row for every planned episode. Metrics are null until complete.",
    ),
    "cells": table(
        {
            **RUN,
            "model": S,
            "communication": MODE,
            "selfish_count": field("integer", enum=[0, 1, 3, 5]),
            "completed_episodes": I,
            "planned_episodes": R,
            **CELL_METRICS,
        },
        ["model", "communication", "selfish_count"],
        "One row per planned model/communication/role cell; means use completed episodes only.",
    ),
    "contrasts": table(
        {
            **RUN,
            "kind": field("string", enum=["model", "communication"]),
            "contrast": S,
            "baseline_value": S,
            "comparison_value": S,
            "model": NS,
            "communication": field("string", nullable=True, enum=[*COMMUNICATION_MODES, "leader"]),
            "selfish_count": field("integer", enum=[0, 1, 3, 5]),
            "matched_seeds": I,
            "seed_ids": field("array", items=I, uniqueItems=True),
            "mean_total_return_difference": N,
            "mean_normalized_difference": N,
            "normalized_ci_lower": N,
            "normalized_ci_upper": N,
        },
        ["kind", "baseline_value", "comparison_value", "model", "communication", "selfish_count"],
        "One planned contrast; difference = comparison minus baseline. CI bounds are null with fewer than two matched seeds.",
    ),
    "status": table(
        {
            **AXES,
            "status": STATUS,
            "current_round": field("integer", nullable=True, minimum=1),
            "phase": field(
                "string",
                nullable=True,
                enum=["pre_round", "action", "midpoint", "discussion", "final", "complete"],
            ),
            "rounds_completed": I,
            **USAGE_TOTALS,
        },
        ["episode_id"],
        "One row per planned episode. The cursor round can have an unfinished action phase.",
    ),
    "actions": table(
        {
            **AXES,
            "round": R,
            "player": S,
            "role": ROLE,
            "opponent": S,
            "action": field("string", enum=["C", "D"]),
            "opponent_action": field("string", enum=["C", "D"]),
            "payoff": field("integer", enum=[0, 1, 3, 5]),
            "cumulative_payoff": I,
        },
        ["episode_id", "round", "player"],
        "One row per player per committed encounter round, including incomplete episodes.",
    ),
    "beliefs": table(
        {
            **AXES,
            "round": R,
            "phase": field("string", enum=["action", "final"]),
            "player": S,
            "role": ROLE,
            "target": S,
            "probability": field("number", minimum=0, maximum=1),
            "is_true": BOOL,
            "strategy": TEXT,
        },
        ["episode_id", "round", "phase", "player", "target"],
        "One row per target per committed report. Marginal reports contain player IDs only; legacy categorical reports also include 'none'.",
    ),
    "messages": table(
        {
            **AXES,
            "after_round": I,
            "phase": field("string", enum=["pre_round", "midpoint", "discussion"]),
            "sender": S,
            "recipient": NS,
            "visibility": field("string", enum=["private", "opponent", "public"]),
            "content": TEXT,
        },
        ["episode_id", "after_round", "phase", "sender"],
        "One committed message or note. Pre-round messages precede after_round + 1; opponent-only messages name a recipient. Other recipients are null.",
    ),
    "elections": table(
        {
            **AXES,
            "after_round": R,
            "voter": S,
            "vote": S,
            "voter_role": ROLE,
            "winner": S,
            "winner_role": ROLE,
            "tie": BOOL,
        },
        ["episode_id", "after_round", "voter"],
        "One legacy secret ballot per voter; observer-only. Empty for rotating-v4.",
    ),
    "leader_assignments": table(
        {
            **AXES,
            "before_round": R,
            "leader": S,
            "leader_role": ROLE,
        },
        ["episode_id"],
        "One predetermined leader per leader episode, recorded at setup; observer-only.",
    ),
    "usage": table(
        {
            **AXES,
            "request_id": S,
            "player": S,
            "round": R,
            "phase": PHASE,
            "attempt": R,
            "accepted": BOOL,
            "response_model": NS,
            "provider": NS,
            "prompt_tokens": field("integer", nullable=True, minimum=0),
            "completion_tokens": field("integer", nullable=True, minimum=0),
            "reported_cost_usd": field("number", nullable=True, minimum=0),
            "request_file": S,
        },
        ["episode_id", "request_id", "attempt"],
        "One received model-response attempt, including invalid responses. Transport failures stay in raw request logs.",
    ),
    "events": table(
        {
            **AXES,
            "event_id": S,
            "sequence": R,
            "round": R,
            "phase": PHASE,
            "type": field(
                "string", enum=["belief", "encounter", "midpoint", "election", "discussion", "leader_assignment"]
            ),
            "payload": field("object"),
        },
        ["episode_id", "event_id"],
        "One committed event, ordered by sequence within an episode. Payload follows the type discriminator.",
    ),
}


def obj(properties):
    return {
        "type": "object",
        "properties": properties,
        "required": list(properties),
        "additionalProperties": False,
    }


PAYLOADS = {
    "leader_assignment": obj({"leader": S, "role": ROLE}),
    "belief": obj(
        {
            "player": S,
            "beliefs": {
                "type": "object",
                "additionalProperties": field("number", minimum=0, maximum=1),
            },
            "strategy": TEXT,
        }
    ),
    "encounter": obj(
        {
            "players": field("array", items=S, minItems=2, maxItems=2),
            "actions": field(
                "array", items=field("string", enum=["C", "D"]), minItems=2, maxItems=2
            ),
            "payoffs": field(
                "array", items=field("integer", enum=[0, 1, 3, 5]), minItems=2, maxItems=2
            ),
        }
    ),
    "discussion": obj(
        {
            "visibility": MODE,
            "posts": field(
                "array",
                items=obj(
                    {
                        "sender": S,
                        "content": TEXT,
                        "recipient": NS,
                        "visibility": field("string", enum=["private", "opponent", "public"]),
                    }
                ),
            ),
        }
    ),
    "midpoint": obj({"player": S, "content": TEXT, "vote": NS}),
    "election": obj(
        {
            "winner": S,
            "votes": {"type": "object", "additionalProperties": S},
            "counts": {"type": "object", "additionalProperties": I},
            "tied_candidates": field("array", items=S, minItems=1),
        }
    ),
}
PAYLOADS["belief"]["properties"]["action"] = field("string", nullable=True, enum=["C", "D"])
PAYLOADS["belief"]["required"].append("action")
TABLES["events"]["allOf"] = [
    {"if": {"properties": {"type": {"const": kind}}}, "then": {"properties": {"payload": schema}}}
    for kind, schema in PAYLOADS.items()
]


def schema():
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "https://github.com/shaowuz/intentional-agent/schemas/visualization-v4",
        "title": "Intentional Agent visualization bundle v4",
        **obj(
            {
                "schema_version": {"const": VERSION},
                "run_id": RUN["run_id"],
                "snapshot_id": field("string", pattern="^[0-9a-f]{64}$"),
                "status": field("string", enum=["complete", "incomplete"]),
                "tables": obj(
                    {name: field("array", items={"$ref": f"#/$defs/{name}"}) for name in TABLES}
                ),
            }
        ),
        "$defs": TABLES,
    }


def canonical_bytes(value):
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    ).encode("utf-8")


def snapshot_id(bundle):
    return hashlib.sha256(
        canonical_bytes({k: v for k, v in bundle.items() if k != "snapshot_id"})
    ).hexdigest()


def validate_bundle(bundle):
    # Reject NaN/Infinity even though Python's JSON parser accepts them.
    canonical_bytes(bundle)
    try:
        jsonschema.Draft202012Validator(
            schema(), format_checker=jsonschema.FormatChecker()
        ).validate(bundle)
    except jsonschema.ValidationError as exc:
        raise ValueError(
            f"Visualization schema violation ({exc.validator}) at {list(exc.absolute_path)}"
        ) from None
    if bundle["snapshot_id"] != snapshot_id(bundle):
        raise ValueError("Snapshot digest mismatch")
    episodes = {r["episode_id"]: r for r in bundle["tables"]["episodes"]}
    for name, rows in bundle["tables"].items():
        seen = set()
        for row in rows:
            if row["run_id"] != bundle["run_id"]:
                raise ValueError(f"{name}: run_id differs from bundle")
            key = tuple(row[k] for k in TABLES[name]["x-primary-key"])
            if key in seen:
                raise ValueError(f"{name}: duplicate primary key {key}")
            seen.add(key)
            if "episode_id" in row:
                parent = episodes.get(row["episode_id"])
                if parent is None or any(row[k] != parent[k] for k in AXES):
                    raise ValueError(f"{name}: episode identity/axes mismatch")
    if {r["episode_id"] for r in bundle["tables"]["status"]} != set(episodes):
        raise ValueError("Episode and status coverage differ")
    for row in bundle["tables"]["status"]:
        if row["status"] != episodes[row["episode_id"]]["status"]:
            raise ValueError("Episode and status completion flags differ")
    for row in episodes.values():
        if row["status"] != "complete" and any(row[k] is not None for k in METRICS):
            raise ValueError("Incomplete episode has final metrics")
    expected_status = (
        "complete"
        if all(row["status"] == "complete" for row in episodes.values())
        else "incomplete"
    )
    if bundle["status"] != expected_status:
        raise ValueError("Bundle and episode completion flags differ")
    return bundle


def csv_value(value):
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (list, dict)):
        return canonical_bytes(value).decode("utf-8")
    return str(value)


def csv_text(name, rows):
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(
        buffer,
        fieldnames=list(TABLES[name]["properties"]),
        extrasaction="raise",
        lineterminator="\n",
    )
    writer.writeheader()
    writer.writerows({k: csv_value(v) for k, v in row.items()} for row in rows)
    return buffer.getvalue()


def atomic_text(path, text):
    fd, temp = tempfile.mkstemp(prefix=".export-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def event_rows(events):
    counts = {}
    result = []
    for event in events:
        ep = event["episode_id"]
        counts[ep] = counts.get(ep, 0) + 1
        kind = event["type"]
        phase = event.get(
            "phase",
            {
                "encounter": "action",
                "discussion": "discussion",
                "election": "midpoint",
                "midpoint": "midpoint",
            }.get(kind),
        )
        payload = {
            k: v
            for k, v in event.items()
            if k not in {*AXES, "type", "round", "after_round", "phase"}
        }
        if kind == "belief":
            payload.setdefault("action", None)
        elif kind == "midpoint":
            payload.setdefault("vote", None)
        elif kind == "discussion":
            payload["posts"] = [{"recipient": None, **p} for p in payload["posts"]]
        result.append(
            {
                **{k: event[k] for k in AXES if k != "run_id"},
                "event_id": f"{ep}:{counts[ep]:06d}",
                "sequence": counts[ep],
                "round": (
                    event["after_round"] + 1 if phase == "pre_round" else
                    event.get("round", event.get("after_round"))
                ),
                "phase": phase,
                "type": kind,
                "payload": payload,
            }
        )
    return result


def publish(
    output,
    manifest,
    result,
    summaries,
    statuses,
    actions,
    beliefs,
    messages,
    elections,
    usage,
    events,
    leader_assignments,
):
    """Publish a validated atomic bundle plus deterministic CSV/JSONL mirrors."""
    output = Path(output)
    with exclusive_run(output, lock_name=".exports.lock"):
        identity = output / "output_identity.json"
        if not identity.exists():
            write_json(identity, {"run_id": str(uuid4())})
        run_id = read_json(identity)["run_id"]
        complete = {s["episode_id"]: s for s in summaries}
        plans = {p["episode_id"]: p["config"] for p in manifest["plan"]}
        episodes = []
        for status in statuses:
            s = complete.get(status["episode_id"], {})
            config = plans[status["episode_id"]]
            episodes.append(
                {
                    **{k: status[k] for k in AXES if k != "run_id"},
                    "status": status["status"],
                    **{
                        k: config[k]
                        for k in (
                            "protocol_version",
                            "players",
                            "rounds",
                            "reasoning_effort",
                            "selfish_persona",
                        )
                    },
                    **{k: s.get(k) for k in METRICS},
                    "belief_format": (
                        "marginal" if config["protocol_version"] in ("rotating-v3", "rotating-v4")
                        else "categorical"
                    ),
                    "leader": s.get("leader"),
                    "selfish_players": s.get("selfish_players"),
                    **{k: status[k] for k in USAGE_TOTALS},
                }
            )
        cells = [
            {
                **{
                    k: c[k]
                    for k in (
                        "model",
                        "communication",
                        "selfish_count",
                        "completed_episodes",
                        "planned_episodes",
                    )
                },
                **{
                    ("selfish_leader_rate" if k == "leader_is_selfish" else k): c[k]
                    for k in METRICS
                },
            }
            for c in result["cells"]
        ]
        contrasts = []
        for c in result["contrasts"]:
            interval = c["normalized_bootstrap_95pct_interval"]
            contrasts.append(
                {
                    **{
                        k: c[k]
                        for k in TABLES["contrasts"]["properties"]
                        if k not in ("run_id", "normalized_ci_lower", "normalized_ci_upper")
                    },
                    "normalized_ci_lower": interval[0] if interval else None,
                    "normalized_ci_upper": interval[1] if interval else None,
                }
            )
        tables = {
            "episodes": episodes,
            "cells": cells,
            "contrasts": contrasts,
            "status": statuses,
            "actions": actions,
            "beliefs": beliefs,
            "messages": messages,
            "elections": elections,
            "leader_assignments": leader_assignments,
            "usage": usage,
            "events": event_rows(events),
        }
        for name, rows in tables.items():
            columns = TABLES[name]["properties"]
            rows[:] = [{k: run_id if k == "run_id" else row[k] for k in columns} for row in rows]
            # Deterministic order independent of generation or provider completion order.
            rows.sort(
                key=lambda row: canonical_bytes([row[k] for k in TABLES[name]["x-primary-key"]])
            )
        bundle = scrub(
            {
                "schema_version": VERSION,
                "run_id": run_id,
                "snapshot_id": "",
                "status": result["status"],
                "tables": tables,
            }
        )
        bundle["snapshot_id"] = snapshot_id(bundle)
        validate_bundle(bundle)
        write_json(output / "visualization.schema.json", schema())
        for name, rows in bundle["tables"].items():
            atomic_text(output / f"{name}.csv", csv_text(name, rows))
        atomic_text(
            output / "timeline.jsonl",
            "".join(
                json.dumps(row, ensure_ascii=False, allow_nan=False) + "\n"
                for row in bundle["tables"]["events"]
            ),
        )
        # Consumers can fetch this one file atomically; no cross-file read races.
        write_json(output / "visualization.json", bundle)
        return bundle


def load_bundle(path):
    return validate_bundle(read_json(path))


def validate_output(output):
    output = Path(output)
    with exclusive_run(output, lock_name=".exports.lock"):
        bundle = load_bundle(output / "visualization.json")
        for name, rows in bundle["tables"].items():
            if (output / f"{name}.csv").read_text(encoding="utf-8") != csv_text(name, rows):
                raise ValueError(f"{name}.csv differs from the canonical bundle")
        timeline = [
            json.loads(line)
            for line in (output / "timeline.jsonl").read_text(encoding="utf-8").splitlines()
        ]
        if timeline != bundle["tables"]["events"]:
            raise ValueError("timeline.jsonl differs from the canonical bundle")
        if read_json(output / "visualization.schema.json") != schema():
            raise ValueError("Exported schema differs from the supported contract")
        return {
            "status": "valid",
            "schema_version": VERSION,
            "run_id": bundle["run_id"],
            "snapshot_id": bundle["snapshot_id"],
            "row_counts": {name: len(rows) for name, rows in bundle["tables"].items()},
        }


def typescript_type(value):
    if "const" in value:
        return json.dumps(value["const"])
    if "enum" in value:
        return " | ".join(json.dumps(v) for v in value["enum"])
    kind = value.get("type")
    if isinstance(kind, list):
        return " | ".join(typescript_type({**value, "type": k}) for k in kind)
    if kind == "null":
        return "null"
    if kind in ("number", "integer"):
        return "number"
    if kind == "array":
        return f"Array<{typescript_type(value['items'])}>"
    if kind == "object":
        if "properties" in value:
            return (
                "{ "
                + "; ".join(
                    f"{json.dumps(k)}: {typescript_type(v)}" for k, v in value["properties"].items()
                )
                + " }"
            )
        additional = value.get("additionalProperties")
        return f"Record<string, {typescript_type(additional) if isinstance(additional, dict) else 'unknown'}>"
    return kind


def typescript():
    lines = [
        "// Generated by scripts/generate_output_contract.py; do not edit manually.",
        f"export const SCHEMA_VERSION = {json.dumps(VERSION)} as const;",
        "",
    ]
    for name, definition in TABLES.items():
        title = name.title() + "Row"
        if name == "events":
            lines.append("export type EventsRow = {")
            for k, v in definition["properties"].items():
                if k not in ("type", "payload"):
                    lines.append(f"  {k}: {typescript_type(v)};")
            lines.append("} & (")
            for kind, payload in PAYLOADS.items():
                lines.append(
                    f"  | {{ type: {json.dumps(kind)}; payload: {typescript_type(payload)} }}"
                )
            lines.append(");\n")
            continue
        lines.append(f"export interface {title} {{")
        lines.extend(f"  {k}: {typescript_type(v)};" for k, v in definition["properties"].items())
        lines.append("}\n")
    lines += [
        "export interface VisualizationBundle {",
        "  schema_version: typeof SCHEMA_VERSION;",
        "  run_id: string;",
        "  snapshot_id: string;",
        '  status: "complete" | "incomplete";',
        "  tables: {",
    ]
    lines += [f"    {name}: {name.title()}Row[];" for name in TABLES]
    lines += ["  };", "}", ""]
    return "\n".join(lines)

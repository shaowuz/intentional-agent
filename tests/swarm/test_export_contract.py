import copy
import csv
import json
from pathlib import Path

import pytest
from swarm_game.cli import main
from swarm_game.export_contract import (
    TABLES,
    VERSION,
    load_bundle,
    schema,
    snapshot_id,
    typescript,
    validate_bundle,
    validate_output,
)
from swarm_game.matrix import run_matrix
from swarm_game.matrix_analysis import analyze_matrix
from swarm_game.providers import Completion, ProviderError, ScriptedProvider

ROOT = Path(__file__).resolve().parents[2]


def spec(**overrides):
    return {
        "game": {"protocol_version": "rotating-v2", "backend": "scripted", "players": 2, "rounds": 2},
        "seeds": [7], **overrides,
    }


@pytest.fixture(scope="module")
def complete_output(tmp_path_factory):
    output = tmp_path_factory.mktemp("visualization_fixture") / "run"
    run_matrix(spec(), output, progress=lambda _: None)
    return output


def test_generated_schema_and_types_have_no_drift():
    assert (
        json.loads((ROOT / "docs/visualization/visualization.schema.json").read_text()) == schema()
    )
    assert (ROOT / "docs/visualization/types.ts").read_text() == typescript()


def test_all_conditions_share_the_contract_and_stable_identifiers(complete_output):
    bundle = load_bundle(complete_output / "visualization.json")
    receipt = validate_output(complete_output)
    assert receipt["status"] == "valid" and receipt["schema_version"] == VERSION
    assert receipt["row_counts"]["episodes"] == receipt["row_counts"]["status"] == 12
    assert {e["communication"] for e in bundle["tables"]["episodes"]} == {
        "none",
        "public",
        "leader",
    }
    assert len({e["model"] for e in bundle["tables"]["episodes"]}) == 2
    for name, rows in bundle["tables"].items():
        columns = list(TABLES[name]["properties"])
        assert all(set(r) == set(columns) for r in rows)
        with (complete_output / f"{name}.csv").open(newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            assert reader.fieldnames == columns
            csv_rows = list(reader)
        assert len(csv_rows) == len(rows)
    for e in bundle["tables"]["episodes"]:
        assert e["good_total_return"] == 6 * (2 - e["selfish_count"])
        assert (
            (type(e["leader_is_selfish"]) is bool)
            if e["communication"] == "leader"
            else e["leader_is_selfish"] is None
        )
    for c in bundle["tables"]["cells"]:
        assert "selfish_leader_rate" in c and "leader_is_selfish" not in c
    for c in bundle["tables"]["contrasts"]:
        assert c["baseline_value"] and c["comparison_value"]
        assert c["normalized_ci_lower"] is None and c["normalized_ci_upper"] is None
    assert {e["type"] for e in bundle["tables"]["events"]} == {
        "belief",
        "encounter",
        "midpoint",
        "election",
        "discussion",
    }
    for episode in bundle["tables"]["episodes"]:
        events = [e for e in bundle["tables"]["events"] if e["episode_id"] == episode["episode_id"]]
        assert [e["sequence"] for e in events] == list(range(1, len(events) + 1))
    before = (complete_output / "visualization.json").read_bytes()
    analyze_matrix(complete_output)
    assert (complete_output / "visualization.json").read_bytes() == before
    assert main(["validate-output", str(complete_output)]) == 0


@pytest.mark.parametrize(
    "bad",
    [
        "version",
        "boolean",
        "extra_field",
        "null_field",
        "duplicate",
        "foreign_key",
        "nonfinite",
        "digest",
    ],
)
def test_reader_rejects_invalid_exports(complete_output, bad):
    bundle = copy.deepcopy(load_bundle(complete_output / "visualization.json"))
    if bad == "version":
        bundle["schema_version"] = "intentional-agent.visualization/999"
    elif bad == "boolean":
        bundle["tables"]["usage"][0]["accepted"] = "True"
    elif bad == "extra_field":
        bundle["tables"]["actions"][0]["surprise"] = 1
    elif bad == "null_field":
        del bundle["tables"]["episodes"][0]["leader"]
    elif bad == "duplicate":
        bundle["tables"]["actions"].append(bundle["tables"]["actions"][0])
    elif bad == "foreign_key":
        bundle["tables"]["beliefs"][0]["episode_id"] = "missing"
    elif bad == "nonfinite":
        bundle["tables"]["beliefs"][0]["probability"] = float("nan")
    if bad not in ("digest", "nonfinite"):
        bundle["snapshot_id"] = snapshot_id(bundle)
    elif bad == "digest":
        bundle["snapshot_id"] = "0" * 64
    with pytest.raises(ValueError):
        validate_bundle(bundle)


def test_empty_tables_keep_headers_and_missing_values(tmp_path):
    class Fail(ScriptedProvider):
        def complete(self, *args, **kwargs):
            raise ProviderError("fixture interruption")

    output = tmp_path / "empty"
    one = spec(models=["openai/gpt-6-luna"], communication_modes=["none"], selfish_counts=[0])
    with pytest.raises(ProviderError):
        run_matrix(one, output, provider_factory=Fail, progress=lambda _: None)
    bundle = load_bundle(output / "visualization.json")
    for name in ("actions", "beliefs", "messages", "elections", "leader_assignments", "usage", "events", "contrasts"):
        assert bundle["tables"][name] == []
        assert (output / f"{name}.csv").read_text().strip() == ",".join(TABLES[name]["properties"])
    assert bundle["tables"]["episodes"][0]["good_total_return"] is None
    assert bundle["tables"]["cells"][0]["good_total_return"] is None
    assert bundle["tables"]["status"][0]["rounds_completed"] == 0
    assert validate_output(output)["status"] == "valid"


def test_partial_committed_events_and_resume_keep_identity(tmp_path):
    class FailMidpoint(ScriptedProvider):
        def complete(self, req, *args, **kwargs):
            if req.phase == "midpoint" and req.player == "P2":
                raise ProviderError("stop before simultaneous midpoint commit")
            return super().complete(req, *args, **kwargs)

    output = tmp_path / "partial"
    one = spec(models=["openai/gpt-6-luna"], communication_modes=["leader"], selfish_counts=[1])
    with pytest.raises(ProviderError):
        run_matrix(one, output, provider_factory=FailMidpoint, progress=lambda _: None)
    before = load_bundle(output / "visualization.json")
    assert len(before["tables"]["actions"]) == 2
    assert len(before["tables"]["messages"]) == 2
    assert all(m["phase"] == "pre_round" for m in before["tables"]["messages"])
    assert before["tables"]["elections"] == []
    assert before["tables"]["status"][0]["rounds_completed"] == 1
    assert before["tables"]["episodes"][0]["good_total_return"] is None
    before_ids = [e["event_id"] for e in before["tables"]["events"]]
    run_matrix(one, output, resume=True, progress=lambda _: None)
    after = load_bundle(output / "visualization.json")
    assert before["run_id"] == after["run_id"]
    assert before["snapshot_id"] != after["snapshot_id"]
    assert [e["event_id"] for e in after["tables"]["events"]][: len(before_ids)] == before_ids
    assert after["tables"]["episodes"][0]["status"] == "complete"
    assert validate_output(output)["status"] == "valid"


def test_interrupted_opponent_exchange_stays_private_and_resumes(tmp_path):
    accepted = []

    class FailExchange(ScriptedProvider):
        def complete(self, req, *args, **kwargs):
            if req.phase == "pre_round" and req.player == "P2":
                raise ProviderError("interrupt opponent exchange")
            accepted.append((req.round, req.phase, req.player))
            return super().complete(req, *args, **kwargs)

    output = tmp_path / "exchange"
    one = spec(models=["openai/gpt-6-luna"], communication_modes=["leader"], selfish_counts=[1])
    with pytest.raises(ProviderError):
        run_matrix(one, output, provider_factory=FailExchange, progress=lambda _: None)
    before = load_bundle(output / "visualization.json")
    assert before["tables"]["messages"] == before["tables"]["events"] == []
    assert before["tables"]["status"][0]["phase"] == "pre_round"
    assert before["tables"]["status"][0]["rounds_completed"] == 0

    class Resume(ScriptedProvider):
        def complete(self, req, *args, **kwargs):
            assert (req.round, req.phase, req.player) not in accepted
            accepted.append((req.round, req.phase, req.player))
            if req.phase == "action" and req.round == 1:
                posts = req.view["discussion_history"][0]["posts"]
                assert {p["sender"] for p in posts} == {"P1", "P2"}
            return super().complete(req, *args, **kwargs)

    run_matrix(one, output, resume=True, provider_factory=Resume, progress=lambda _: None)
    after = load_bundle(output / "visualization.json")
    exchange = [m for m in after["tables"]["messages"] if m["phase"] == "pre_round"]
    assert len(exchange) == 2
    assert all(m["after_round"] == 0 and m["visibility"] == "opponent" for m in exchange)
    assert {(m["sender"], m["recipient"]) for m in exchange} == {("P1", "P2"), ("P2", "P1")}
    first = after["tables"]["events"][0]
    assert (first["type"], first["phase"], first["round"]) == ("discussion", "pre_round", 1)
    assert len(accepted) == after["tables"]["episodes"][0]["completed_model_responses"] == 12
    assert validate_output(output)["status"] == "valid"


def test_csv_roundtrips_unicode_empty_text_newlines_and_booleans(tmp_path):
    text = '"quoted", multi\nline — 你好 🙂'

    class TextProvider(ScriptedProvider):
        def complete(self, req, *args, **kwargs):
            response = super().complete(req, *args, **kwargs)
            if req.phase in ("midpoint", "discussion"):
                data = json.loads(response.content)
                data["content"] = "" if req.player == "P1" else text
                return Completion(json.dumps(data, ensure_ascii=False), response.metadata)
            return response

    output = tmp_path / "text"
    run_matrix(
        spec(models=["openai/gpt-6-luna"], communication_modes=["public"], selfish_counts=[0]),
        output,
        provider_factory=TextProvider,
        progress=lambda _: None,
    )
    bundle = load_bundle(output / "visualization.json")
    with (output / "messages.csv").open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert {r["content"] for r in rows} == {"", text}
    assert {r["content"] for r in bundle["tables"]["messages"]} == {"", text}
    with (output / "usage.csv").open(newline="", encoding="utf-8") as f:
        assert {r["accepted"] for r in csv.DictReader(f)} == {"true"}
    with (output / "episodes.csv").open(newline="", encoding="utf-8") as f:
        assert next(csv.DictReader(f))["leader_is_selfish"] == ""
    assert validate_output(output)["status"] == "valid"
    (output / "messages.csv").write_text("corrupted")
    with pytest.raises(ValueError, match="messages.csv"):
        validate_output(output)
    assert load_bundle(output / "visualization.json") == bundle


def test_published_visualization_fixtures_are_valid_and_scripted():
    for name in ("complete", "incomplete"):
        bundle = load_bundle(ROOT / f"docs/visualization/examples/{name}.json")
        assert bundle["status"] == name
        assert {e["backend"] for e in bundle["tables"]["episodes"]} == {"scripted"}
        assert {e["protocol_version"] for e in bundle["tables"]["episodes"]} == {"rotating-v4"}
        assert bundle["tables"]["elections"] == []
        if name == "complete":
            assert {e["communication"] for e in bundle["tables"]["episodes"]} == {
                "none", "public", "opponent", "good_leader", "selfish_leader",
            }
            assert {e["selfish_count"] for e in bundle["tables"]["episodes"]} == {1, 3, 5}
            assert len(bundle["tables"]["leader_assignments"]) == 12


def test_valid_probability_rounding_does_not_break_export(tmp_path):
    class Rounded(ScriptedProvider):
        def complete(self, req, *args, **kwargs):
            response = super().complete(req, *args, **kwargs)
            if req.phase in ("action", "final"):
                data = json.loads(response.content)
                data["beliefs"] = dict.fromkeys(data["beliefs"], 0.0)
                other = [p for p in req.view["players"] if p != req.player]
                data["beliefs"][other[0]] = 1.0
                data["beliefs"][other[1]] = 0.000001
                return Completion(json.dumps(data), response.metadata)
            return response

    output = tmp_path / "rounding"
    configuration = spec(
        models=["openai/gpt-6-luna"], communication_modes=["none"], selfish_counts=[0]
    )
    configuration["game"]["players"] = 4
    run_matrix(configuration, output, provider_factory=Rounded, progress=lambda _: None)
    bundle = load_bundle(output / "visualization.json")
    assert 2 < bundle["tables"]["episodes"][0]["mean_brier_score"] < 2.000002

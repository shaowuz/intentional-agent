import copy
import json
from dataclasses import replace

import httpx
import pytest

from swarm_game.config import COMMUNICATION_MODES, Config
from swarm_game.cli import main
from swarm_game.export_contract import load_bundle, validate_output
from swarm_game.game import commit_phase, initial_state
from swarm_game.matrix import run_matrix
from swarm_game.matrix_analysis import analyze_matrix
from swarm_game.protocol import make_request, validate_response
from swarm_game.providers import OpenRouterProvider, ProviderError, ScriptedProvider
from swarm_game.storage import read_json, write_json


def config_for(mode="none", count=1, **overrides):
    return Config(**{
        "protocol_version": "rotating-v4", "communication": mode,
        "selfish_count": count, "players": 10, "rounds": 10,
        "backend": "scripted", **overrides,
    })


@pytest.mark.parametrize("count", [1, 3, 5])
def test_predetermined_leaders_and_matched_design(count):
    reference = initial_state(config_for(count=count))
    for mode in COMMUNICATION_MODES:
        config = config_for(mode, count)
        state = initial_state(config)
        assert state == initial_state(config)
        assert state == initial_state(replace(config, model="anthropic/claude-haiku-5.5"))
        for key in ("players", "roles", "schedule"):
            assert state[key] == reference[key]
        assert state["election"] is None and state["midpoint_reports"] == {}
        assignment = state["leader_assignment"]
        if mode in ("good_leader", "selfish_leader"):
            role = "good" if mode == "good_leader" else "selfish"
            assert assignment["role"] == state["roles"][assignment["leader"]] == role
            assert assignment["round"] == 1
        else:
            assert assignment is None


@pytest.mark.parametrize("mode", COMMUNICATION_MODES)
@pytest.mark.parametrize("count", [1, 3, 5])
def test_all_rounds_route_only_permitted_messages(mode, count):
    config = config_for(mode, count)
    state = initial_state(config)
    provider = ScriptedProvider(config)
    assignment = copy.deepcopy(state["leader_assignment"])
    calls = 0
    for round_number in range(1, 11):
        assert (state["round"], state["phase"]) == (round_number, "pre_round")
        requests = {p: make_request(state, config, p) for p in state["players"]}
        for player, req in requests.items():
            assert len(req.view["encounters"]) == round_number - 1
            assert req.view["opponent"] != player
            response = {"content": f"message-{round_number}-{player}-end"}
            validate_response(response, req, config)
            state["pending"][player] = response
            assert all(make_request(state, config, p) == old for p, old in requests.items())
            calls += 1
        commit_phase(state, config)
        assert (state["round"], state["phase"]) == (round_number, "action")
        for player in state["players"]:
            req = make_request(state, config, player)
            expected = {player}
            if mode == "public":
                expected = set(state["players"])
            elif mode == "opponent":
                expected.add(req.view["opponent"])
            elif assignment:
                expected.add(assignment["leader"])
            posts = req.view["discussion_history"][-1]["posts"]
            assert {p["sender"] for p in posts} == expected
            for post in posts:
                if mode == "opponent":
                    assert post["visibility"] == "opponent"
                    assert post["recipient"] in {player, req.view["opponent"]}
                    assert post["recipient"] != post["sender"]
                else:
                    assert post["recipient"] is None
                    public = mode == "public" or (
                        assignment is not None and post["sender"] == assignment["leader"]
                    )
                    assert post["visibility"] == ("public" if public else "private")
            for other in set(state["players"]) - expected:
                assert f"message-{round_number}-{other}-end" not in json.dumps(req.to_dict())
            state["pending"][player] = json.loads(provider.complete(req).content)
            calls += 1
        commit_phase(state, config)
        assert state["leader_assignment"] == assignment
        assert state["midpoint_reports"] == {} and state["election"] is None
    assert state["phase"] == "final"
    for player in state["players"]:
        req = make_request(state, config, player)
        state["pending"][player] = json.loads(provider.complete(req).content)
        calls += 1
    commit_phase(state, config)
    assert state["completed"] and calls == config.expected_requests == 210
    assert len(state["discussions"]) == 10
    assert set(state["payoffs"].values()) == {30}


@pytest.mark.parametrize("phase", ["pre_round", "action", "final"])
def test_audience_requests_and_provider_metadata_hide_leader_role(phase, monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "fake-fixture-key")
    good_config = config_for("good_leader", 3)
    bad_config = replace(good_config, communication="selfish_leader")
    good = initial_state(good_config)
    leader = good["leader_assignment"]["leader"]
    swapped = next(p for p in good["players"] if good["roles"][p] == "selfish")
    bad = copy.deepcopy(good)
    bad["roles"][leader], bad["roles"][swapped] = "selfish", "good"
    bad["leader_assignment"]["role"] = "selfish"
    for state, config in ((good, good_config), (bad, bad_config)):
        provider = ScriptedProvider(config)
        # Include committed messages, prior private reports, and encounter histories.
        while state["round"] < 2 or state["phase"] != "pre_round":
            state["pending"] = {
                p: json.loads(provider.complete(make_request(state, config, p)).content)
                for p in state["players"]
            }
            commit_phase(state, config)
        state["phase"] = phase
    for player in set(good["players"]) - {leader, swapped}:
        good_req = make_request(good, good_config, player)
        bad_req = make_request(bad, bad_config, player)
        assert good_req == bad_req
        assert good_req.view["communication"] == "leader"
        assert good_req.view["leader"] == leader
        serialized = json.dumps(good_req.to_dict())
        for forbidden in ("good_leader", "selfish_leader", "leader_assignment", "leader_role"):
            assert forbidden not in serialized
        assert all(e["opponent"] != player for e in good_req.view["encounters"])
        with httpx.Client(transport=httpx.MockTransport(
            lambda _: pytest.fail("privacy test made an HTTP request")
        )) as client:
            a = OpenRouterProvider(good_config, client=client).payload(good_req)
            b = OpenRouterProvider(bad_config, client=client).payload(bad_req)
            assert a == b


@pytest.mark.parametrize("mode", COMMUNICATION_MODES)
def test_interrupted_exchange_and_assignment_exports_resume(tmp_path, mode):
    spec = {
        "models": ["openai/gpt-6-luna"], "communication_modes": [mode],
        "selfish_counts": [3], "seeds": [2],
        "game": {"backend": "scripted", "players": 6, "rounds": 2},
    }
    output = tmp_path / mode
    accepted = []

    class Interrupted(ScriptedProvider):
        def complete(self, req, *args, **kwargs):
            if req.round == 1 and req.phase == "pre_round" and req.player == "P2":
                raise ProviderError("interrupt initial simultaneous exchange")
            accepted.append((req.round, req.phase, req.player))
            return super().complete(req, *args, **kwargs)

    with pytest.raises(ProviderError):
        run_matrix(spec, output, provider_factory=Interrupted, progress=lambda _: None)
    before = load_bundle(output / "visualization.json")
    assert before["tables"]["actions"] == before["tables"]["messages"] == []
    assert before["tables"]["elections"] == []
    assignments = before["tables"]["leader_assignments"]
    has_leader = mode in ("good_leader", "selfish_leader")
    assert len(assignments) == int(has_leader)
    assert [e["type"] for e in before["tables"]["events"]] == (
        ["leader_assignment"] if has_leader else []
    )
    assert before["tables"]["status"][0]["rounds_completed"] == 0
    if has_leader:
        assert assignments[0]["leader_role"] == ("good" if mode == "good_leader" else "selfish")
        first = before["tables"]["events"][0]
        assert first["round"] == 1 and first["phase"] == "setup"
    assert validate_output(output)["status"] == "valid"

    class Resume(ScriptedProvider):
        def complete(self, req, *args, **kwargs):
            identity = (req.round, req.phase, req.player)
            assert identity not in accepted
            accepted.append(identity)
            return super().complete(req, *args, **kwargs)

    run_matrix(spec, output, resume=True, provider_factory=Resume, progress=lambda _: None)
    after = load_bundle(output / "visualization.json")
    assert after["run_id"] == before["run_id"]
    assert after["tables"]["leader_assignments"] == assignments
    assert after["tables"]["elections"] == []
    assert {e["type"] for e in after["tables"]["events"]} <= {
        "leader_assignment", "discussion", "belief", "encounter",
    }
    assert after["tables"]["episodes"][0]["completed_model_responses"] == len(accepted) == 30
    assert validate_output(output)["status"] == "valid"
    if has_leader:
        checkpoint = next((output / "episodes").glob("*/checkpoint.json"))
        state = read_json(checkpoint)
        state["leader_assignment"]["role"] = "tampered"
        write_json(checkpoint, state)
        with pytest.raises(ValueError, match="leader assignment"):
            analyze_matrix(output)


@pytest.mark.parametrize("mode", COMMUNICATION_MODES)
def test_one_round_episode_and_message_budget(mode):
    config = config_for(mode, rounds=1)
    state = initial_state(config)
    provider = ScriptedProvider(config)
    req = make_request(state, config, "P1")
    with pytest.raises(ValueError, match="96"):
        validate_response({"content": "x " * 100}, req, config)
    with pytest.raises(ValueError):
        validate_response({"content": "", "recipient": "P2"}, req, config)
    phases = []
    while not state["completed"]:
        phases.append(state["phase"])
        state["pending"] = {
            p: json.loads(provider.complete(make_request(state, config, p)).content)
            for p in state["players"]
        }
        commit_phase(state, config)
    assert phases == ["pre_round", "action", "final"]
    assert config.expected_requests == 30


def test_cli_uses_final_protocol_and_predetermined_leader(tmp_path, capsys):
    output = tmp_path / "cli"
    assert main([
        "run", "--backend", "scripted", "--communication", "selfish_leader",
        "--selfish-count", "5", "--rounds", "1", "--output", str(output),
    ]) == 0
    result = json.loads(capsys.readouterr().out)
    config = read_json(output / "manifest.json")["config"]
    state = read_json(output / "checkpoint.json")
    assert config["protocol_version"] == "rotating-v4"
    assert config["players"] == 10
    assert result["usage"]["completed_model_responses"] == 30
    assert result["leader_is_selfish"] is True
    assert state["leader_assignment"]["role"] == "selfish"
    assert state["election"] is None and state["midpoint_reports"] == {}

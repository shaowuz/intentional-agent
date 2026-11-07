import csv
import json
from dataclasses import replace

import httpx
import pytest
from swarm_game.cli import main
from swarm_game.config import COMMUNICATION_MODES, Config
from swarm_game.game import commit_phase, initial_state, player_view
from swarm_game.matrix import episode_plan, normalize_spec, preview, run_matrix
from swarm_game.matrix_analysis import analyze_matrix
from swarm_game.protocol import make_request, validate_response
from swarm_game.providers import OpenRouterProvider, ProviderError, ScriptedProvider
from swarm_game.storage import read_json, write_json


def advance(state, config):
    provider = ScriptedProvider(config)
    state["pending"] = {
        p: json.loads(provider.complete(make_request(state, config, p)).content)
        for p in state["players"]
    }
    commit_phase(state, config)


def reach_midpoint(config):
    state = initial_state(config)
    while state["phase"] != "midpoint":
        advance(state, config)
    return state


def tiny_spec():
    return {
        "game": {"protocol_version": "rotating-v2", "players": 2, "rounds": 2, "backend": "scripted"},
        "seeds": [7],
    }


def test_design_counts_models_and_matching():
    spec = normalize_spec({})
    plan = episode_plan(spec)
    info = preview(spec)
    assert info["episodes"] == 360
    assert info["encounters"] == 18000
    assert info["requests_before_retries"] == 75600
    assert info["requests_per_episode"] == dict.fromkeys(COMMUNICATION_MODES, 210)
    assert info["midpoint_after_round"] is None
    assert spec["game"]["protocol_version"] == "rotating-v4"
    assert spec["selfish_counts"] == [1, 3, 5]
    assert spec["models"] == ["openai/gpt-6-luna", "anthropic/claude-haiku-5.5"]
    assert spec["game"]["selfish_persona"] == "neutral"
    for seed in spec["seeds"]:
        states = [initial_state(Config(**p["config"])) for p in plan if p["config"]["seed"] == seed]
        assert all(s["schedule"] == states[0]["schedule"] for s in states)
        for k in (1, 3, 5):
            roles = [
                initial_state(Config(**p["config"]))["roles"]
                for p in plan
                if p["config"]["seed"] == seed and p["config"]["selfish_count"] == k
            ]
            assert all(r == roles[0] for r in roles)
            assert sum(role == "selfish" for role in roles[0].values()) == k
    assert plan == episode_plan(spec)


@pytest.mark.parametrize(
    "change",
    [
        {"models": []},
        {"models": ["unknown/model"]},
        {"seeds": [1, 1]},
        {"seeds": [True]},
        {"selfish_counts": [2]},
        {"selfish_counts": [True]},
        {"communication_modes": ["friends"]},
        {"game": {"model": "openai/gpt-6-luna"}},
        {"game": {"selfish_persona": "trump_like"}},
        {"game": {"protocol_version": "rotating-v1"}},
        {"game": {"rounds": 0}},
        {"communication_modes": ["leader"]},
        {"unknown": 1},
    ],
)
def test_invalid_matrix(change):
    with pytest.raises(ValueError):
        normalize_spec(change)


@pytest.mark.parametrize("rounds", [2, 5, 10])
@pytest.mark.parametrize("protocol_version,selfish_count", [
    ("rotating-v2", 1), ("rotating-v3", 5),
])
def test_opponent_messages_precede_every_pre_election_round(rounds, protocol_version, selfish_count):
    config = Config(
        protocol_version=protocol_version, communication="leader",
        players=10, rounds=rounds, selfish_count=selfish_count, backend="scripted",
    )
    state = initial_state(config)
    for round_number in range(1, config.midpoint_round + 1):
        assert (state["round"], state["phase"]) == (round_number, "pre_round")
        requests = {p: make_request(state, config, p) for p in state["players"]}
        for player, request in requests.items():
            pair = next(p for p in state["schedule"][round_number - 1] if player in p)
            assert request.view["opponent"] == next(p for p in pair if p != player)
            assert len(request.view["encounters"]) == round_number - 1
            assert not {"roles", "schedule", "pending"} & request.view.keys()
            assert "private message to your current opponent" in request.messages[0]["content"]
            with pytest.raises(ValueError):
                validate_response({"content": "", "recipient": player}, request, config)
            with pytest.raises(ValueError, match="96"):
                validate_response({"content": "x " * 100}, request, config)
            state["pending"][player] = {"content": f"message-{round_number}-{player}"}
            assert all(
                make_request(state, config, p) == req for p, req in requests.items()
            )
        commit_phase(state, config)
        assert (state["round"], state["phase"]) == (round_number, "action")
        for player in state["players"]:
            request = make_request(state, config, player)
            opponent = request.view["opponent"]
            posts = request.view["discussion_history"][-1]["posts"]
            assert {p["sender"] for p in posts} == {player, opponent}
            assert all(p["visibility"] == "opponent" for p in posts)
            assert all(
                p["recipient"] == (opponent if p["sender"] == player else player)
                for p in posts
            )
            for outsider in set(state["players"]) - {player, opponent}:
                assert json.dumps(f"message-{round_number}-{outsider}") not in json.dumps(
                    request.view
                )
        advance(state, config)
    assert state["phase"] == "midpoint"
    advance(state, config)
    assert state["phase"] == "discussion"
    advance(state, config)
    assert state["round"] == config.midpoint_round + 1
    while not state["completed"]:
        assert state["phase"] != "pre_round"
        advance(state, config)
    assert len(state["discussions"]) == rounds
    assert sum(d["phase"] == "pre_round" for d in state["discussions"]) == rounds // 2


def test_secret_simultaneous_ballots_and_selfish_leader():
    config = Config(
        protocol_version="rotating-v2",
        communication="leader",
        rounds=4,
        backend="scripted",
        selfish_count=1,
    )
    state = reach_midpoint(config)
    assert state["round"] == 2
    assert len(state["encounters"]) == 6
    for player in state["players"]:
        for d in player_view(state, config, player)["discussion_history"]:
            pair = next(
                pair for pair in state["schedule"][d["after_round"]] if player in pair
            )
            assert {p["sender"] for p in d["posts"]} == set(pair)
    selfish = next(p for p, role in state["roles"].items() if role == "selfish")
    before = make_request(state, config, "P2")
    state["pending"]["P1"] = {"vote": selfish, "content": "private ballot sentinel"}
    assert make_request(state, config, "P2") == before
    for player in state["players"]:
        state["pending"][player] = {"vote": selfish, "content": f"ballot-{player}"}
        validate_response(state["pending"][player], make_request(state, config, player), config)
    commit_phase(state, config)
    assert state["election"]["winner"] == selfish
    assert state["phase"] == "discussion" and state["round"] == 2
    for player in state["players"]:
        view = player_view(state, config, player)
        assert view["leader"] == selfish
        assert view["own_midpoint_report"]["content"] == f"ballot-{player}"
        assert not {"votes", "counts", "roles", "schedule", "pending"} & view.keys()
        assert "ballot-" + next(p for p in state["players"] if p != player) not in json.dumps(view)
    state["pending"] = {
        p: {"content": "I am good. Follow my advice." if p == selfish else f"secret-{p}"}
        for p in state["players"]
    }
    commit_phase(state, config)
    for player in state["players"]:
        view = player_view(state, config, player)
        last = view["discussion_history"][-1]["posts"]
        assert {p["sender"] for p in last} == {player, selfish}
        assert (
            next(p["content"] for p in last if p["sender"] == selfish)
            == "I am good. Follow my advice."
        )
    while not state["completed"]:
        advance(state, config)
    for d in state["discussions"]:
        public = [p for p in d["posts"] if p["visibility"] == "public"]
        assert len(public) == (d["after_round"] >= config.midpoint_round)
        if public:
            assert public[0]["sender"] == selfish


def test_ties_control_reflections_and_validation():
    base = Config(
        protocol_version="rotating-v2", communication="leader", rounds=3, backend="scripted"
    )
    state = reach_midpoint(base)
    req = make_request(state, base, "P1")
    with pytest.raises(ValueError):
        validate_response({"vote": "outsider", "content": ""}, req, base)
    with pytest.raises(ValueError, match="96"):
        validate_response({"vote": "P1", "content": "x " * 100}, req, base)
    advance(state, base)
    winner = state["election"]["winner"]
    other = reach_midpoint(replace(base, model="anthropic/claude-haiku-5.5"))
    advance(other, base)
    assert other["election"]["winner"] == winner
    assert len(other["election"]["tied_candidates"]) == 6
    for mode in ("none", "public"):
        cfg = replace(base, communication=mode)
        control = reach_midpoint(cfg)
        control["pending"] = {p: {"content": f"private-{p}"} for p in control["players"]}
        commit_phase(control, cfg)
        assert control["election"] is None
        view = player_view(control, cfg, "P1")
        assert "private-P1" in json.dumps(view) and "private-P2" not in json.dumps(view)


def test_matrix_preview_never_constructs_provider(tmp_path, monkeypatch, capsys):
    from swarm_game import matrix

    monkeypatch.setattr(matrix, "run_matrix", lambda *a, **kw: pytest.fail("preview executed"))
    config = tmp_path / "spec.json"
    write_json(config, {})
    output = tmp_path / "unused"
    assert main(["matrix", "--config", str(config), "--output", str(output)]) == 0
    assert json.loads(capsys.readouterr().out)["episodes"] == 360
    assert not output.exists()


def test_matrix_tables_pairing_and_resume(tmp_path):
    output = tmp_path / "suite"
    result = run_matrix(tiny_spec(), output, progress=lambda _: None)
    assert result["status"] == "complete" and result["completed_episodes"] == 12
    assert result["usage_including_incomplete"]["completed_model_responses"] == 128
    assert all(c["return_per_good_encounter"] == 3 for c in result["cells"])
    assert all(c["mean_total_return_difference"] == 0 for c in result["contrasts"])
    assert all(c["normalized_bootstrap_95pct_interval"] is None for c in result["contrasts"])
    assert len(result["contrasts"]) == 18
    with (output / "actions.csv").open() as f:
        assert len(list(csv.DictReader(f))) == 48
    with (output / "elections.csv").open() as f:
        assert len(list(csv.DictReader(f))) == 8
    assert "Scripted test output" in (output / "report.html").read_text()
    assert (output / "runtime/swarm_game/prompts/midpoint.txt").is_file()

    class NoCalls(ScriptedProvider):
        def complete(self, *a, **kw):
            pytest.fail("resume replayed a response")

    assert (
        run_matrix(
            tiny_spec(), output, resume=True, provider_factory=NoCalls, progress=lambda _: None
        )
        == result
    )
    with pytest.raises(ValueError, match="configuration or source"):
        run_matrix({**tiny_spec(), "seeds": [8]}, output, resume=True)
    state_path = next((output / "episodes").glob("*/checkpoint.json"))
    state = read_json(state_path)
    state["roles"]["P1"] = "tampered"
    write_json(state_path, state)
    with pytest.raises(ValueError, match="schedules/roles"):
        analyze_matrix(output)


def test_interrupted_matrix_tracks_all_missing_cells_and_resumes(tmp_path):
    class Fail(ScriptedProvider):
        def complete(self, *a, **kw):
            raise ProviderError("interrupted fixture")

    output = tmp_path / "interrupted"
    with pytest.raises(ProviderError):
        run_matrix(tiny_spec(), output, provider_factory=Fail, progress=lambda _: None)
    partial = read_json(output / "analysis.json")
    assert partial["status"] == "incomplete" and partial["completed_episodes"] == 0
    assert len(partial["missing_episodes"]) == 12
    assert all(c["good_total_return"] is None for c in partial["cells"])
    assert (
        run_matrix(tiny_spec(), output, resume=True, progress=lambda _: None)["status"]
        == "complete"
    )


def test_anthropic_routing_and_medium_catalog(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "fake-fixture-key")
    config = Config(model="anthropic/claude-haiku-5.5")
    observed = []

    def handler(req):
        if req.method == "GET":
            return httpx.Response(
                200,
                json={
                    "data": [
                        {
                            "id": config.model,
                            "supported_parameters": ["reasoning", "response_format", "max_tokens"],
                            "reasoning": {"supported_efforts": ["medium"]},
                        }
                    ]
                },
            )
        observed.append(json.loads(req.content))
        return httpx.Response(
            200,
            json={
                "model": config.model,
                "provider": "Anthropic",
                "choices": [{"message": {"content": "{}"}, "finish_reason": "stop"}],
            },
        )

    provider = OpenRouterProvider(
        config,
        client=httpx.Client(
            base_url="https://openrouter.ai/api/v1/", transport=httpx.MockTransport(handler)
        ),
    )
    assert provider.catalog_entry()["id"] == config.model
    provider.complete(make_request(initial_state(config), config, "P1"))
    assert observed[0]["provider"] == {
        "only": ["anthropic"],
        "allow_fallbacks": False,
        "require_parameters": True,
    }
    assert observed[0]["reasoning"] == {"effort": "medium", "exclude": True}
    assert "temperature" not in observed[0]

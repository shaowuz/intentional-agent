import copy
import json

import pytest

from swarm_game.analysis import score_state
from swarm_game.config import Config
from swarm_game.export_contract import load_bundle, validate_output
from swarm_game.game import initial_state
from swarm_game.matrix import run_matrix
from swarm_game.protocol import make_request, validate_response
from swarm_game.providers import ScriptedProvider, prior_beliefs
from swarm_game.storage import read_json


def configuration(**changes):
    return Config(**{
        "protocol_version": "rotating-v3", "players": 10, "rounds": 10,
        "selfish_count": 1, "backend": "scripted", **changes,
    })


def test_nested_roles_and_hidden_actual_count():
    previous = set()
    views = {}
    for count in (1, 3, 5):
        config = configuration(selfish_count=count)
        state = initial_state(config)
        selfish = {p for p, role in state["roles"].items() if role == "selfish"}
        assert len(selfish) == count and previous <= selfish
        previous = selfish
        for player in state["players"]:
            req = make_request(state, config, player)
            key = (player, state["roles"][player])
            if key in views:
                assert req == views[key]
            views[key] = req
            assert req.view["selfish_count_options"] == [1, 3, 5]
            assert not {"roles", "selfish_count", "selfish_players"} & req.view.keys()
            assert set(req.schema["properties"]["beliefs"]["properties"]) == set(state["players"])
            assert "each have probability 1/3" in req.messages[0]["content"]
            prior = prior_beliefs(req.view)
            own_selfish = state["roles"][player] == "selfish"
            expected_other = 26 / 81 if own_selfish else 55 / 189
            assert prior[player] == float(own_selfish)
            assert all(
                value == pytest.approx(expected_other)
                for p, value in prior.items() if p != player
            )
            data = json.loads(ScriptedProvider(config).complete(req).content)
            validate_response(data, req, config)
            assert sum(data["beliefs"].values()) > 1
            invalid = copy.deepcopy(data)
            invalid["beliefs"][player] = float(not own_selfish)
            with pytest.raises(ValueError):
                validate_response(invalid, req, config)
            invalid = copy.deepcopy(data)
            invalid["beliefs"]["none"] = 0
            with pytest.raises(ValueError):
                validate_response(invalid, req, config)
            invalid = copy.deepcopy(data)
            invalid["beliefs"] = dict.fromkeys(state["players"], 0)
            with pytest.raises(ValueError):
                validate_response(invalid, req, config)


@pytest.mark.parametrize("changes", [
    {"selfish_count": 0}, {"selfish_count": 2}, {"selfish_count": 7},
    {"selfish_count": True}, {"players": 4},
])
def test_invalid_multi_selfish_configuration(changes):
    with pytest.raises(ValueError):
        configuration(**changes)


def test_multi_selfish_matrix_metrics_exports_and_resume(tmp_path):
    spec = {
        "models": ["openai/gpt-6-luna"], "selfish_counts": [1, 3, 5],
        "seeds": [3], "game": {"players": 6, "rounds": 2, "backend": "scripted"},
    }
    output = tmp_path / "multi"
    result = run_matrix(spec, output, progress=lambda _: None)
    assert result["completed_episodes"] == 15
    assert result["usage_including_incomplete"]["completed_model_responses"] == 450
    bundle = load_bundle(output / "visualization.json")
    assert validate_output(output)["status"] == "valid"
    assert {c["selfish_count"] for c in bundle["tables"]["cells"]} == {1, 3, 5}
    for episode in bundle["tables"]["episodes"]:
        count = episode["selfish_count"]
        selfish = set(episode["selfish_players"])
        assert len(selfish) == count
        assert episode["belief_format"] == "marginal"
        assert episode["good_total_return"] == 6 * (6 - count)
        assert episode["return_per_good_encounter"] == 3
        assert episode["good_good_return"] + episode["good_selfish_return"] == episode["good_total_return"]
        assert episode["final_correct_none_rate"] is None
        if episode["leader"]:
            assert episode["leader_is_selfish"] == (episode["leader"] in selfish)
        reports = [
            b for b in bundle["tables"]["beliefs"]
            if b["episode_id"] == episode["episode_id"]
        ]
        assert {b["target"] for b in reports if b["is_true"]} == selfish
        assert all(b["target"] != "none" for b in reports)
        state = read_json(output / "episodes" / episode["episode_id"] / "checkpoint.json")
        config = read_json(output / "episodes" / episode["episode_id"] / "manifest.json")["config"]
        for record in state["belief_records"]:
            record["beliefs"] = {p: float(p in selfish) for p in state["players"]}
        # Pick another selfish player when available to catch single-target scoring.
        if state["election"]:
            state["election"]["winner"] = sorted(selfish)[-1]
        if state["leader_assignment"]:
            state["leader_assignment"].update(leader=sorted(selfish)[-1], role="selfish")
        perfect = score_state(state, config)
        assert perfect["mean_brier_score"] == perfect["final_mean_brier_score"] == 0
        assert perfect["final_identification_rate"] == 1
        if state["election"] or state["leader_assignment"]:
            assert perfect["leader_is_selfish"] is True
        for record in state["belief_records"]:
            if record["phase"] == "final" and state["roles"][record["player"]] == "good":
                record["beliefs"] = {
                    p: float(p == sorted(selfish)[0]) for p in state["players"]
                }
        partial = score_state(state, config)
        assert partial["final_identification_rate"] == pytest.approx(1 / count)
        assert partial["final_mean_brier_score"] == pytest.approx((count - 1) / 5)

    class NoCalls(ScriptedProvider):
        def complete(self, *args, **kwargs):
            pytest.fail("completed multi-selfish episode replayed a response")

    assert run_matrix(
        spec, output, resume=True, provider_factory=NoCalls, progress=lambda _: None
    ) == result

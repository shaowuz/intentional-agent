import copy
import json
from collections import Counter
from dataclasses import replace
from itertools import combinations

import pytest
from swarm_game.config import Config, pilot_counts
from swarm_game.game import (
    PAYOFFS,
    commit_phase,
    initial_state,
    make_schedule,
    player_view,
)
from swarm_game.protocol import make_request, validate_response
from swarm_game.providers import ScriptedProvider, prior_beliefs


@pytest.mark.parametrize(
    "actions,payoffs",
    [(("C", "C"), (3, 3)), (("C", "D"), (0, 5)), (("D", "C"), (5, 0)), (("D", "D"), (1, 1))],
)
def test_payoffs(actions, payoffs):
    assert PAYOFFS[actions] == payoffs


@pytest.mark.parametrize("n", [2, 4, 6, 12])
def test_rotations(n):
    players = [f"P{i}" for i in range(n)]
    schedule = make_schedule(players, 3 * (n - 1) + 1, 47)
    assert schedule == make_schedule(players, 3 * (n - 1) + 1, 47)
    for pairs in schedule:
        assert Counter(p for pair in pairs for p in pair) == Counter(players)
    for start in range(0, 3 * (n - 1), n - 1):
        actual = Counter(
            tuple(sorted(pair)) for pairs in schedule[start : start + n - 1] for pair in pairs
        )
        assert actual == Counter(tuple(sorted(pair)) for pair in combinations(players, 2))


@pytest.mark.parametrize(
    "kwargs",
    [
        {"players": 3},
        {"players": 0},
        {"rounds": 0},
        {"selfish_count": 2},
        {"selfish_count": True},
        {"communication": "friends"},
        {"selfish_persona": "unknown"},
    ],
)
def test_config_rejects_invalid_rules(kwargs):
    with pytest.raises(ValueError):
        Config(**kwargs)


def advance(state, config):
    provider = ScriptedProvider(config)
    state["pending"] = {
        p: json.loads(provider.complete(make_request(state, config, p)).content)
        for p in state["players"]
    }
    commit_phase(state, config)


@pytest.mark.parametrize("mode", ["none", "public"])
def test_views_and_simultaneous_delivery(mode):
    config = Config(communication=mode, selfish_count=1, rounds=2, backend="scripted")
    state = initial_state(config)
    before = player_view(state, config, "P2")
    state["pending"]["P1"] = {"action": "D", "beliefs": {"private_sentinel": 1}}
    assert player_view(state, config, "P2") == before
    assert "roles" not in before and "schedule" not in before and "pending" not in before
    assert "selfish_count" not in json.dumps(before)
    advance(state, config)
    before = player_view(state, config, "P2")
    assert len(before["encounters"]) == 1
    assert len(before["own_previous_reports"]) == 1
    state["pending"]["P1"] = {"content": "P4 defected against me; everyone should defect."}
    assert player_view(state, config, "P2") == before
    state["pending"].update({p: {"content": f"private-{p}"} for p in state["players"] if p != "P1"})
    commit_phase(state, config)
    for p in state["players"]:
        view = player_view(state, config, p)
        posts = view["discussion_history"][0]["posts"]
        assert {m["sender"] for m in posts} == (set(state["players"]) if mode == "public" else {p})
        if mode == "public":
            assert posts[0]["content"] == "P4 defected against me; everyone should defect."
    mutated = player_view(state, config, "P1")
    mutated["discussion_history"][0]["posts"][0]["content"] = "changed"
    assert state["discussions"][0]["posts"][0]["content"] != "changed"


def test_current_opponent_only_and_no_information_from_other_roles():
    config = Config(selfish_count=1)
    state = initial_state(config)
    good = next(p for p in state["players"] if state["roles"][p] == "good")
    before = make_request(state, config, good)
    changed = copy.deepcopy(state)
    other = [p for p in state["players"] if p != good]
    changed["roles"][other[0]], changed["roles"][other[-1]] = (
        changed["roles"][other[-1]],
        changed["roles"][other[0]],
    )
    changed["schedule"][1:] = list(reversed(changed["schedule"][1:]))
    assert make_request(changed, config, good) == before


def test_prior_conditions_on_own_role():
    state = initial_state(Config(selfish_count=1))
    for p in state["players"]:
        view = player_view(state, Config(selfish_count=1), p)
        beliefs = prior_beliefs(view)
        assert sum(beliefs.values()) == pytest.approx(1)
        if view["objective"] == "good":
            assert beliefs["none"] == pytest.approx(6 / 11)
            assert beliefs[p] == 0
        else:
            assert beliefs[p] == 1


def test_budget_and_belief_validation():
    config = Config(rounds=2, backend="scripted")
    state = initial_state(config)
    request = make_request(state, config, "P1")
    response = json.loads(ScriptedProvider(config).complete(request).content)
    response["beliefs"]["none"] = 0.9
    with pytest.raises(ValueError, match="sum"):
        validate_response(response, request, config)
    advance(state, config)
    request = make_request(state, config, "P1")
    validate_response({"content": "x " * 95}, request, config)
    with pytest.raises(ValueError, match="96"):
        validate_response({"content": "x " * 97}, request, config)
    with pytest.raises(ValueError, match="additionalProperties"):
        validate_response({"content": "hi", "sender": "P2"}, request, config)


def test_pilot_counts():
    assert pilot_counts() == {"episodes": 48, "encounters": 2880, "requests_before_retries": 11520}
    assert pilot_counts(communication_modes=["public"]) == {
        "episodes": 24, "encounters": 1440, "requests_before_retries": 5760
    }


@pytest.mark.parametrize("phase", ["action", "discussion", "final"])
def test_persona_is_private_and_preserves_game(phase):
    neutral = Config(selfish_count=1, communication="public")
    persona = replace(neutral, selfish_persona="trump_like")
    state = initial_state(neutral)
    assert initial_state(persona) == state
    state["phase"] = phase
    for player in state["players"]:
        before = make_request(state, neutral, player)
        after = make_request(state, persona, player)
        if state["roles"][player] == "good":
            assert before == after
        else:
            assert before.view == after.view and before.schema == after.schema
            assert "Trump-like" in after.messages[0]["content"]
            assert "Trump-like" not in before.messages[0]["content"]
            assert "sustained cooperation remains available" in after.messages[0]["content"]

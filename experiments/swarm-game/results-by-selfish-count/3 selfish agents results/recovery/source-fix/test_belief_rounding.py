import copy

import pytest

from swarm_game.config import Config
from swarm_game.game import initial_state
from swarm_game.protocol import make_request, validate_response


def action_request(*, objective="selfish", players=10, protocol="rotating-v4"):
    config = Config(
        protocol_version=protocol, players=players, rounds=2,
        selfish_count=1, backend="scripted",
    )
    state = initial_state(config)
    state["phase"] = "action"
    player = next(p for p in state["players"] if state["roles"][p] == objective)
    request = make_request(state, config, player)
    return config, request, [p for p in state["players"] if p != player]


def response(request, others, values):
    return {
        "action": "D", "strategy": "Unchanged strategy.",
        "beliefs": {
            request.player: int(request.view["objective"] == "selfish"),
            **dict(zip(others, values, strict=True)),
        },
    }


@pytest.mark.parametrize("values", [
    [1, 1, 1, *([0.166667] * 6)],
    [*([0.666667] * 6), 0, 0, 0],
])
def test_recorded_six_decimal_rounding_failures_are_accepted_unchanged(values):
    config, request, others = action_request()
    data = response(request, others, values)
    original = copy.deepcopy(data)
    assert validate_response(data, request, config) is data
    assert data == original


@pytest.mark.parametrize("objective,values", [
    ("selfish", [1, 1, 1, 0.500002, 0.500003, 0, 0, 0, 0]),
    ("good", [0.999995, 0, 0, 0, 0, 0, 0, 0, 0]),
])
def test_exact_decimal_tolerance_boundaries_are_inclusive(objective, values):
    config, request, others = action_request(objective=objective)
    data = response(request, others, values)
    validate_response(data, request, config)


@pytest.mark.parametrize("objective,values,total", [
    ("selfish", [1, 1, 1, 0.500003, 0.500003, 0, 0, 0, 0], "5.000006"),
    ("good", [0.999994, 0, 0, 0, 0, 0, 0, 0, 0], "0.999994"),
    ("selfish", [1, 1, 1, 1, 0.1, 0, 0, 0, 0], "5.1"),
])
def test_outside_rounding_budget_reports_actual_sum_and_correction(objective, values, total):
    config, request, others = action_request(objective=objective)
    data = response(request, others, values)
    with pytest.raises(ValueError) as exc:
        validate_response(data, request, config)
    message = str(exc.value)
    assert f"your entries total {total}" in message
    assert "tolerance is 0.0000050" in message
    assert "accepted total 0.9999950 to 5.0000050" in message
    assert "keep your own probability fixed" in message


@pytest.mark.parametrize("last,accepted", [(1.0, True), (0.999997, True), (0.999996, False)])
def test_rounding_budget_scales_with_six_player_report(last, accepted):
    config, request, others = action_request(objective="good", players=6)
    data = response(request, others, [last, 0, 0, 0, 0])
    if accepted:
        validate_response(data, request, config)
    else:
        with pytest.raises(ValueError, match="tolerance is 0.0000030"):
            validate_response(data, request, config)


@pytest.mark.parametrize("bad", [-0.000001, 1.000001, "0.5", float("nan"), float("inf")])
def test_individual_probability_validation_is_not_relaxed(bad):
    config, request, others = action_request()
    data = response(request, others, [0.3] * 9)
    data["beliefs"][others[0]] = bad
    with pytest.raises(ValueError):
        validate_response(data, request, config)


def test_own_role_missing_and_extra_fields_are_still_rejected():
    config, request, others = action_request()
    data = response(request, others, [0.3] * 9)
    for change in ("own_role", "missing", "extra"):
        invalid = copy.deepcopy(data)
        if change == "own_role":
            invalid["beliefs"][request.player] = 0.999999
        elif change == "missing":
            invalid["beliefs"].pop(others[0])
        else:
            invalid["beliefs"]["none"] = 0
        with pytest.raises(ValueError):
            validate_response(invalid, request, config)


def test_legacy_distribution_sum_tolerance_is_unchanged():
    config, request, others = action_request(objective="good", protocol="rotating-v2")
    data = response(request, others, [0.1] * 9)
    data["beliefs"]["none"] = 0.100002
    with pytest.raises(ValueError, match="beliefs must sum to 1"):
        validate_response(data, request, config)

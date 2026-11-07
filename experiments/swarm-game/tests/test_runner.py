import pytest

from swarm_game.analysis import analyze_comparison, score_state
from swarm_game.config import Config
from swarm_game.providers import Completion, ProviderError, ScriptedProvider
from swarm_game.runner import EpisodeError, run_episode
from swarm_game.storage import read_json, write_json


@pytest.mark.parametrize("mode", ["none", "public"])
@pytest.mark.parametrize("k", [0, 1])
def test_full_episodes_cooperative_selfish(tmp_path, mode, k):
    config = Config(communication=mode, selfish_count=k, backend="scripted")
    output = tmp_path / "episode"
    summary = run_episode(config, ScriptedProvider(config), output)
    state = read_json(output / "checkpoint.json")
    assert summary["good_total_return"] == 60 * (6 - k)
    assert summary["return_per_good_encounter"] == 3
    assert summary["good_cooperation_rate"] == 1
    assert summary["usage"]["completed_model_responses"] == 240
    assert len(state["encounters"]) == 60
    assert len(state["discussions"]) == 19
    assert state["discussions"][0]["after_round"] == 1
    assert state["discussions"][-1]["after_round"] == 19
    assert summary["false_accusation_observations"] == 0
    assert (output / "report.md").exists()


@pytest.mark.parametrize(
    "policy,selfish_policy,total,gg,gs",
    [
        ("defect", "defect", 100, 80, 20),
        ("cooperate", "defect", 240, 240, 0),
        ("tit_for_tat", "defect", 255, 240, 15),
    ],
)
def test_known_policy_scores(tmp_path, policy, selfish_policy, total, gg, gs):
    config = Config(
        selfish_count=1, backend="scripted", policy=policy, selfish_policy=selfish_policy
    )
    summary = run_episode(config, ScriptedProvider(config), tmp_path / "episode")
    assert (
        summary["good_total_return"],
        summary["good_good_return"],
        summary["good_selfish_return"],
    ) == (total, gg, gs)


class InterruptingProvider(ScriptedProvider):
    def __init__(self, config, fail_at=None):
        super().__init__(config)
        self.calls = 0
        self.fail_at = fail_at

    def complete(self, *args, **kwargs):
        self.calls += 1
        if self.calls == self.fail_at:
            raise ProviderError("simulated interruption")
        return super().complete(*args, **kwargs)


def test_resume_reuses_completed_responses(tmp_path):
    config = Config(backend="scripted", players=4, rounds=2)
    output = tmp_path / "interrupted"
    with pytest.raises(ProviderError):
        run_episode(config, InterruptingProvider(config, fail_at=3), output)
    state = read_json(output / "checkpoint.json")
    assert len(state["pending"]) == 2 and not state["encounters"]
    # Simulate a crash after a durable response but before checkpointing it.
    state["pending"].pop("P2")
    write_json(output / "checkpoint.json", state)
    provider = InterruptingProvider(config)
    resumed = run_episode(config, provider, output, resume=True)
    assert provider.calls == config.expected_requests - 2
    fresh = run_episode(config, ScriptedProvider(config), tmp_path / "fresh")
    assert resumed == fresh
    assert not (output / "error.json").exists()


class InvalidProvider(ScriptedProvider):
    def __init__(self, config, recover):
        super().__init__(config)
        self.calls = 0
        self.recover = recover

    def complete(self, *args, **kwargs):
        self.calls += 1
        if self.calls == 1 or not self.recover:
            return Completion("bad json", {"model": "scripted", "usage": {}})
        return super().complete(*args, **kwargs)


@pytest.mark.parametrize("recover", [True, False])
def test_invalid_response_does_not_become_defection(tmp_path, recover):
    config = Config(players=2, rounds=1, backend="scripted")
    provider = InvalidProvider(config, recover)
    output = tmp_path / "episode"
    if recover:
        result = run_episode(config, provider, output)
        assert result["good_cooperation_rate"] == 1
        assert provider.calls == config.expected_requests + 1
    else:
        with pytest.raises(EpisodeError):
            run_episode(config, provider, output)
        assert provider.calls == 2
        assert not read_json(output / "checkpoint.json")["encounters"]


def test_paired_analysis_and_schedule_identity(tmp_path):
    for k in (0, 1):
        states = []
        for mode in ("none", "public"):
            config = Config(selfish_count=k, communication=mode, backend="scripted", rounds=2)
            output = tmp_path / f"{k}-{mode}"
            run_episode(config, ScriptedProvider(config), output)
            states.append(read_json(output / "checkpoint.json"))
        assert states[0]["schedule"] == states[1]["schedule"]
        assert states[0]["roles"] == states[1]["roles"]
    result = analyze_comparison(tmp_path)
    for effect in result["effects_by_selfish_count"].values():
        assert effect["matched_seed_blocks"] == 1
        assert effect["mean_public_minus_none_total"] == 0
        assert effect["normalized_bootstrap_95pct_interval"] is None


def test_detection_and_false_accusations(tmp_path):
    config = Config(selfish_count=1, rounds=2, backend="scripted")
    output = tmp_path / "episode"
    run_episode(config, ScriptedProvider(config), output)
    state = read_json(output / "checkpoint.json")
    selfish = next(p for p, r in state["roles"].items() if r == "selfish")
    for record in state["belief_records"]:
        record["beliefs"] = {p: float(p == selfish) for p in ["none", *state["players"]]}
    summary = score_state(state, config.to_dict())
    assert summary["mean_brier_score"] == 0
    assert summary["final_identification_rate"] == 1
    assert summary["good_agents_identifying_before_personal_encounter"] == 5
    config0 = Config(rounds=2, backend="scripted")
    state["roles"] = dict.fromkeys(state["players"], "good")
    summary = score_state(state, config0.to_dict())
    assert summary["false_accusation_observations"] == 5 * 3


def test_protect_existing_output_and_changed_config(tmp_path):
    config = Config(players=2, rounds=1, backend="scripted")
    output = tmp_path / "episode"
    run_episode(config, ScriptedProvider(config), output)
    with pytest.raises(FileExistsError):
        run_episode(config, ScriptedProvider(config), output)
    changed = Config(players=2, rounds=2, backend="scripted")
    with pytest.raises(ValueError, match="configuration"):
        run_episode(changed, ScriptedProvider(changed), output, resume=True)

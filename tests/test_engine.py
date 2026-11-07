"""Behavioral tests for game rules, private views, and durable phase barriers."""

import asyncio
from copy import deepcopy
import json

import pytest
from pydantic import ValidationError

from intentional_agent.engine import advance_round, build_observation, create_experiment, payoff, record_event
from intentional_agent.models import ExperimentConfig


class RecordingRuntime:
    def __init__(self, action="C", failure=None):
        self.action = action
        self.failure = failure
        self.calls = []

    async def act(self, agent, observation, phase, state):
        self.calls.append((agent["id"], phase, deepcopy(observation)))
        if self.failure is not None:
            response = self.failure(agent, observation, phase, state, self.calls)
            if response is not None:
                return response
        if phase == "decision":
            return {"action": self.action}
        if phase == "post":
            return {"content": f"Round {observation['round']} report from {agent['id']}.", "parent_id": None}
        visible = observation.get("forum", [])
        return {"content": "I have read the reports." if visible else "", "parent_id": visible[0]["id"] if visible else None}


def run_round(state, runtime, on_update=None):
    return asyncio.run(advance_round(state, runtime, on_update))


def config(**changes):
    values = {"agents": 4, "group1_count": 3, "rounds": 2}
    values.update(changes)
    return ExperimentConfig(**values)


@pytest.mark.parametrize("actions,expected", [(('C', 'C'), (3, 3)), (('C', 'D'), (0, 5)), (('D', 'C'), (5, 0)), (('D', 'D'), (1, 1))])
def test_payoff_matrix(actions, expected):
    assert payoff(*actions) == expected


@pytest.mark.parametrize("actions", [("c", "D"), ("D", "refuse"), ("C", None)])
def test_invalid_actions_have_no_payoff(actions):
    with pytest.raises(ValueError):
        payoff(*actions)


@pytest.mark.parametrize("actions", [("C", "C"), ("C", "D"), ("D", "C"), ("D", "D")])
def test_settlement_uses_matrix_for_actual_pair_orientation(actions):
    def choose(_agent, _observation, phase, _state, calls):
        if phase == "decision":
            return {"action": actions[len(calls) - 1]}

    state = create_experiment(config(agents=2, group1_count=1, rounds=1))
    run_round(state, RecordingRuntime(failure=choose))
    match = state["matches"][0]
    assert (match["action_a"], match["action_b"]) == actions
    assert (match["payoff_a"], match["payoff_b"]) == payoff(*actions)
    assert sum(agent["payoff"] for agent in state["agents"]) == sum(payoff(*actions))
    assert all(agent["matches"] == 1 for agent in state["agents"])
    assert state["status"] == "completed"


def test_population_and_real_model_validation():
    with pytest.raises(ValidationError, match="Group 1 count"):
        config(agents=2, group1_count=3)
    with pytest.raises(ValidationError, match="Choose a model"):
        config(mode="openrouter")
    assert config(agents=2, group1_count=0, mode="openrouter", model_group2="test/model").group1_count == 0
    with pytest.raises(ValidationError):
        config(budget_usd=float("nan"))


def test_seed_reproduces_pairing_without_encoding_roles_in_ids():
    states = [create_experiment(config(agents=5, group1_count=2, rounds=4, seed=72)) for _ in range(2)]
    assert [agent["id"] for agent in states[0]["agents"]] == [f"agent-{i:03d}" for i in range(1, 6)]
    for state in states:
        runtime = RecordingRuntime()
        for _ in range(4):
            run_round(state, runtime)
        assert len(runtime.calls) == 4 * 4
        assert len(state["matches"]) == 4 * 2
        assert sum(agent["matches"] for agent in state["agents"]) == 16
        for event in [item for item in state["events"] if item["kind"] == "round_paired"]:
            pair_ids = [value for pair in event["data"]["pairs"] for value in pair]
            byes = event["data"]["byes"]
            assert len(byes) == 1
            assert len(set(pair_ids)) == 4
            assert not set(pair_ids) & set(byes)
            calls = [call for call in runtime.calls if call[2]["round"] == event["round"]]
            assert byes[0] not in [call[0] for call in calls]
    assert states[0]["matches"] == states[1]["matches"]
    assert [item["group"] for item in states[0]["agents"]] == [item["group"] for item in states[1]["agents"]]
    # Changing the seed can change role assignment independently of public IDs.
    assignments = {tuple(agent["group"] for agent in create_experiment(config(seed=seed))["agents"]) for seed in range(12)}
    assert len(assignments) > 1


@pytest.mark.parametrize("forum", [False, True])
@pytest.mark.parametrize("global_history", [False, True])
@pytest.mark.parametrize("group_score", [False, True])
def test_information_switches_are_independent_and_metadata_is_allowlisted(forum, global_history, group_score):
    state = create_experiment(config(forum_enabled=True))
    run_round(state, RecordingRuntime())
    state["config"].update(forum_enabled=forum, global_history_enabled=global_history, group_score_visible=group_score)
    # Simulate extra researcher metadata being added to records in a future version.
    state["matches"][0]["private_group"] = "DO_NOT_EXPOSE"
    state["forum"][0]["model"] = "DO_NOT_EXPOSE"
    for agent in state["agents"]:
        observation = build_observation(state, agent)
        assert ("forum" in observation) is forum
        assert ("global_history" in observation) is global_history
        assert ("objective_score" in observation) is group_score
        assert "DO_NOT_EXPOSE" not in json.dumps(observation)
        assert "config" not in observation and "agents" not in observation and "group" not in observation
        assert observation["objective"] == state["config"][f"group{agent['group']}_prompt"]
        assert len(observation["private_history"]) == 1
        entry = observation["private_history"][0]
        assert entry["payoff"] == 3
        assert entry["cumulative_payoff"] == 3
        assert set(entry) == {"round", "opponent_id", "action", "opponent_action", "payoff", "cumulative_payoff"}
        if group_score:
            expected = 9 if agent["group"] == 1 else 3
            assert observation["objective_score"] == expected
    observation = build_observation(state, state["agents"][0])
    observation["private_history"][0]["payoff"] = 999
    assert state["matches"][0]["payoff_a"] == 3


def test_decisions_posts_and_replies_each_have_frozen_observations():
    state = create_experiment(config(rounds=2, forum_enabled=True, global_history_enabled=True))
    runtime = RecordingRuntime()
    run_round(state, runtime)
    decisions = [item[2] for item in runtime.calls if item[1] == "decision"]
    posts = [item[2] for item in runtime.calls if item[1] == "post"]
    replies = [item[2] for item in runtime.calls if item[1] == "reply"]
    assert len(decisions) == len(posts) == len(replies) == 4
    assert all(item["private_history"] == [] and item["global_history"] == [] for item in decisions)
    assert all(item["forum"] == [] for item in posts)
    assert all(len(item["global_history"]) == 2 for item in posts)
    assert all(len(item["forum"]) == 4 for item in replies)
    assert all(message["stage"] == "post" for item in replies for message in item["forum"])
    assert len(state["forum"]) == 8
    run_round(state, runtime)
    next_decisions = [item[2] for item in runtime.calls if item[1] == "decision" and item[2]["round"] == 2]
    assert all(len(item["forum"]) == 8 for item in next_decisions)
    assert all({match["round"] for match in item["global_history"]} == {1} for item in next_decisions)


def test_mid_decision_failure_resumes_only_missing_actions_after_json_roundtrip():
    def fail_second(_agent, _observation, _phase, _state, calls):
        if len(calls) == 2:
            raise RuntimeError("A simulated transport failure.")

    state = create_experiment(config(rounds=1))
    first = RecordingRuntime(failure=fail_second)
    run_round(state, first)
    assert state["status"] == "paused"
    assert state["round"] == 0 and state["matches"] == []
    assert len(state["pending"]["decisions"]) == 1
    assert sum(agent["payoff"] for agent in state["agents"]) == 0
    accepted_id = next(iter(state["pending"]["decisions"]))
    resumed = json.loads(json.dumps(state))
    second = RecordingRuntime()
    run_round(resumed, second)
    assert accepted_id not in [item[0] for item in second.calls]
    assert len(second.calls) == 3
    assert resumed["status"] == "completed"
    assert len(resumed["matches"]) == 2
    assert sum(agent["payoff"] for agent in resumed["agents"]) == 12
    assert resumed["error"] is None


@pytest.mark.parametrize("failure_phase", ["post", "reply"])
def test_discussion_failure_never_replays_game_or_completed_messages(failure_phase):
    def fail_second_in_phase(_agent, _observation, phase, _state, calls):
        if phase == failure_phase and sum(item[1] == phase for item in calls) == 2:
            raise RuntimeError("A simulated discussion failure.")

    state = create_experiment(config(rounds=1, forum_enabled=True))
    run_round(state, RecordingRuntime(failure=fail_second_in_phase))
    settled_matches = deepcopy(state["matches"])
    assert state["status"] == "paused"
    assert state["round"] == 1
    assert len(settled_matches) == 2
    assert len(state["forum"]) == (0 if failure_phase == "post" else 4)
    resumed = json.loads(json.dumps(state))
    second = RecordingRuntime()
    run_round(resumed, second)
    assert all(item[1] != "decision" for item in second.calls)
    assert sum(item[1] == failure_phase for item in second.calls) == 3
    assert resumed["matches"] == settled_matches
    assert len(resumed["forum"]) == 8
    assert len({item["id"] for item in resumed["forum"]}) == 8
    assert sum(agent["payoff"] for agent in resumed["agents"]) == 12
    assert resumed["status"] == "completed"


@pytest.mark.parametrize("bad", [{"action": "d"}, {"action": "Refuse"}, {}, {"action": "C", "explanation": "extra"}, {"action": None}, "C"])
def test_invalid_output_pauses_without_defaulting_to_defect(bad):
    state = create_experiment(config())
    runtime = RecordingRuntime(failure=lambda *_args: bad)
    run_round(state, runtime)
    assert state["status"] == "paused"
    assert state["round"] == 0
    assert state["matches"] == []
    assert state["pending"]["decisions"] == {}
    assert all(agent["payoff"] == 0 for agent in state["agents"])


@pytest.mark.parametrize("bad", [{"content": "x" * 4001}, {"content": "Message", "parent_id": "invisible-message"}])
def test_invalid_forum_messages_are_not_published(bad):
    def invalid(_agent, _observation, phase, _state, _calls):
        if phase == "reply":
            return bad

    state = create_experiment(config(rounds=1, forum_enabled=True))
    run_round(state, RecordingRuntime(failure=invalid))
    assert state["status"] == "paused"
    assert len(state["forum"]) == 4
    assert all(item["stage"] == "post" for item in state["forum"])


def test_abstaining_from_forum_is_valid():
    def abstain(_agent, _observation, phase, _state, _calls):
        if phase != "decision":
            return {"content": "", "parent_id": None}

    state = create_experiment(config(rounds=1, forum_enabled=True))
    run_round(state, RecordingRuntime(failure=abstain))
    assert state["status"] == "completed"
    assert state["forum"] == []


@pytest.mark.parametrize("requested_status", ["paused", "stopped"])
def test_controller_can_interrupt_after_a_saved_decision(requested_status):
    state = create_experiment(config(rounds=1))

    async def checkpoint():
        if state.get("pending") and len(state["pending"]["decisions"]) == 1:
            state["status"] = requested_status

    runtime = RecordingRuntime()
    run_round(state, runtime, checkpoint)
    assert state["status"] == requested_status
    assert len(runtime.calls) == 1
    assert len(state["pending"]["decisions"]) == 1
    assert state["matches"] == []
    second = RecordingRuntime()
    run_round(state, second)
    if requested_status == "stopped":
        assert state["status"] == "stopped"
        assert second.calls == []
    else:
        assert state["status"] == "completed"
        assert len(second.calls) == 3


def test_persistence_failure_propagates_with_completed_decision_intact():
    state = create_experiment(config(rounds=1))

    async def broken_checkpoint():
        if state.get("pending") and state["pending"]["decisions"]:
            raise RuntimeError("The database write failed.")

    with pytest.raises(RuntimeError, match="database write"):
        run_round(state, RecordingRuntime(), broken_checkpoint)
    assert len(state["pending"]["decisions"]) == 1
    assert state["matches"] == []


def test_turn_timeout_cancels_work_and_preserves_unsettled_state():
    class SlowRuntime:
        cancelled = False

        async def act(self, _agent, _observation, _phase, _state):
            try:
                await asyncio.sleep(5)
            finally:
                self.cancelled = True

    state = create_experiment(config(rounds=1))
    state["config"]["turn_timeout"] = 0.01
    runtime = SlowRuntime()
    run_round(state, runtime)
    assert runtime.cancelled
    assert state["status"] == "paused"
    assert "turn time limit" in state["error"]
    assert state["matches"] == []
    assert state["pending"]["decisions"] == {}


def test_stop_during_a_runtime_call_never_restarts_or_settles():
    def stop_during_call(_agent, _observation, _phase, state, _calls):
        state["status"] = "stopped"
        return {"action": "C"}

    state = create_experiment(config(rounds=1))
    runtime = RecordingRuntime(failure=stop_during_call)
    run_round(state, runtime)
    assert state["status"] == "stopped"
    assert len(runtime.calls) == 1
    assert len(state["pending"]["decisions"]) == 1
    assert state["matches"] == []


def test_exported_checkpoints_resume_to_the_same_result_as_uninterrupted_run():
    initial = create_experiment(config(rounds=1, forum_enabled=True, global_history_enabled=True))
    uninterrupted = deepcopy(initial)
    snapshots = []

    async def collect_checkpoint():
        snapshots.append(json.loads(json.dumps(uninterrupted)))

    run_round(uninterrupted, RecordingRuntime(), collect_checkpoint)
    # Exercise each distinct collection/publication/settlement checkpoint.
    for snapshot in snapshots:
        if snapshot["status"] == "completed":
            continue
        snapshot["status"] = "paused"
        run_round(snapshot, RecordingRuntime())
        assert snapshot["status"] == "completed"
        assert snapshot["matches"] == uninterrupted["matches"]
        assert snapshot["forum"] == uninterrupted["forum"]
        assert snapshot["agents"] == uninterrupted["agents"]


@pytest.mark.parametrize("crash_phase", ["decision", "post", "reply"])
def test_persisted_terminal_submission_recovers_without_repeating_model_call(crash_phase):
    class CrashAfterSubmission(RecordingRuntime):
        saved = None
        committed_agent_id = None

        async def act(self, agent, observation, phase, state):
            result = await super().act(agent, observation, phase, state)
            if phase == crash_phase:
                record_event(state, "agent_submission", {"format": "tool_call", "result": result}, agent["id"])
                self.saved = json.loads(json.dumps(state))
                self.committed_agent_id = agent["id"]
                # Model output is durable, but the engine has not saved its bucket.
                raise asyncio.CancelledError
            return result

    initial = create_experiment(config(rounds=1, forum_enabled=True))
    uninterrupted = deepcopy(initial)
    run_round(uninterrupted, RecordingRuntime())
    interrupted = deepcopy(initial)
    first = CrashAfterSubmission()
    with pytest.raises(asyncio.CancelledError):
        run_round(interrupted, first)
    resumed = first.saved
    bucket_name = {"decision": "decisions", "post": "posts", "reply": "replies"}[crash_phase]
    assert first.committed_agent_id not in resumed["pending"][bucket_name]
    resumed["status"] = "paused"
    second = RecordingRuntime()
    run_round(resumed, second)
    assert not any(agent_id == first.committed_agent_id and phase == crash_phase for agent_id, phase, _ in second.calls)
    recovered = [event for event in resumed["events"] if event["kind"] == "agent_submission_recovered"]
    assert len(recovered) == 1
    source_id = recovered[0]["data"]["source_event_id"]
    assert any(event["id"] == source_id and event["kind"] == "agent_submission" for event in resumed["events"])
    assert resumed["status"] == "completed"
    assert resumed["matches"] == uninterrupted["matches"]
    assert resumed["forum"] == uninterrupted["forum"]
    assert resumed["agents"] == uninterrupted["agents"]


def paused_before_first_decision():
    state = create_experiment(config(rounds=1))

    async def pause_before_model():
        if state["phase"] == "decision":
            state["status"] = "paused"

    runtime = RecordingRuntime()
    run_round(state, runtime, pause_before_model)
    assert runtime.calls == []
    return state, state["pending"]["pairs"][0][0]


@pytest.mark.parametrize("mutation", [
    {"round": 0},
    {"round": 2},
    {"phase": "post"},
    {"agent_id": "absent-agent"},
    {"kind": "demo_response"},
    {"data": {"format": "json", "result": {"action": "invalid"}}},
    {"data": None},
])
def test_recovery_ignores_unrelated_or_invalid_submission_events(mutation):
    state, target_id = paused_before_first_decision()
    record_event(state, "agent_submission", {"format": "json", "result": {"action": "D"}}, target_id)
    state["events"][-1].update(mutation)
    resumed = json.loads(json.dumps(state))
    runtime = RecordingRuntime()
    run_round(resumed, runtime)
    assert any(agent_id == target_id for agent_id, _, _ in runtime.calls)
    assert not any(event["kind"] == "agent_submission_recovered" for event in resumed["events"])
    assert all(match["action_a"] == match["action_b"] == "C" for match in resumed["matches"])


def test_recovered_result_is_checkpointed_before_scheduling_another_call():
    state, target_id = paused_before_first_decision()
    record_event(state, "agent_submission", {"format": "json", "result": {"action": "D"}}, target_id)
    # A second terminal record cannot replace the original valid commitment.
    record_event(state, "agent_submission", {"format": "json", "result": {"action": "C"}}, target_id)
    saved = []

    async def pause_after_recovery():
        if state["events"][-1]["kind"] == "agent_submission_recovered":
            state["status"] = "paused"
            saved.append(json.loads(json.dumps(state)))

    runtime = RecordingRuntime()
    run_round(state, runtime, pause_after_recovery)
    assert runtime.calls == []
    assert len(saved) == 1
    assert saved[0]["pending"]["decisions"][target_id] == {"action": "D"}
    assert saved[0]["matches"] == []
    resumed = saved[0]
    run_round(resumed, runtime)
    assert all(agent_id != target_id for agent_id, _, _ in runtime.calls)
    match = next(match for match in resumed["matches"] if target_id in (match["a"], match["b"]))
    side = "a" if match["a"] == target_id else "b"
    assert match[f"action_{side}"] == "D"


def test_recovered_reply_must_target_a_message_in_frozen_observation():
    state = create_experiment(config(rounds=1, forum_enabled=True))

    async def pause_before_reply():
        if state["phase"] == "reply":
            state["status"] = "paused"

    run_round(state, RecordingRuntime(), pause_before_reply)
    target_id = state["agents"][0]["id"]
    record_event(state, "agent_submission", {"format": "tool_call", "result": {"content": "A reply", "parent_id": "invisible-parent"}}, target_id)
    runtime = RecordingRuntime()
    run_round(state, runtime)
    assert any(agent_id == target_id and phase == "reply" for agent_id, phase, _ in runtime.calls)
    assert not any(event["kind"] == "agent_submission_recovered" for event in state["events"])
    assert not any(message["parent_id"] == "invisible-parent" for message in state["forum"])

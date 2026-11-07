"""Contract tests use an explicitly mocked OpenRouter transport, never paid inference."""

import asyncio
import copy
import json

import httpx
import pytest

from intentional_agent.runtime import DemoRuntime, OpenRouterRuntime


API_KEY = "test-private-key-must-not-appear"
MODEL = "test/tool-model"


def catalog(*, parameters=None, price="0.000001"):
    return {"data": [{"id": MODEL, "context_length": 1_000_000,
                       "supported_parameters": parameters if parameters is not None else ["tools", "tool_choice", "temperature", "reasoning"],
                       "pricing": {"prompt": price, "completion": price, "request": "0"}}]}


def completion(*, tool=None, arguments=None, content=None, cost=0.002, annotations=None):
    message = {"role": "assistant", "content": content}
    if tool:
        message["tool_calls"] = [{"id": "call-1", "type": "function",
                                  "function": {"name": tool, "arguments": json.dumps(arguments)}}]
    if annotations:
        message["annotations"] = annotations
    usage = {"prompt_tokens": 12, "completion_tokens": 8}
    if cost is not None:
        usage["cost"] = cost
    return {"id": "gen-mocked", "choices": [{"message": message, "finish_reason": "tool_calls" if tool else "stop"}], "usage": usage}


@pytest.fixture
def context():
    state = {"id": "run-test", "round": 0, "events": [], "usage": {}, "config": {
        "model_group1": MODEL, "model_group2": MODEL, "budget_usd": 10,
        "tool_limit": 8, "turn_timeout": 5, "code_timeout": 2,
        "max_tokens": 100, "temperature": 0.7, "reasoning_effort": None,
        "group2_prompt": "SECRET OTHER OBJECTIVE", "mode": "openrouter",
    }, "agents": [{"id": "agent-2", "group": 2, "model": "SECRET OTHER MODEL"}]}
    agent = {"id": "agent-1", "group": 1, "model": MODEL}
    observation = {"agent_id": "agent-1", "round": 1, "opponent_id": "agent-2", "horizon": 20,
                   "objective": "Maximize your designated collective's payoff.", "common_prompt": "Choose C or D.",
                   "private_history": [], "tools": {"files": True, "python": False, "forum": False,
                                                         "global_history": False, "internet": False, "objective_score": False}}
    return state, agent, observation


class Provider:
    def __init__(self, responses, model_catalog=None):
        self.responses = list(responses)
        self.catalog = model_catalog or catalog()
        self.bodies = []
        self.requests = []

    async def __call__(self, request):
        self.requests.append(request)
        if request.url.path.endswith("/models"):
            return httpx.Response(200, json=self.catalog)
        assert request.url.path.endswith("/chat/completions")
        assert request.headers["Authorization"] == f"Bearer {API_KEY}"
        self.bodies.append(json.loads(request.content))
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        if isinstance(response, tuple):
            return httpx.Response(response[0], json=response[1])
        return httpx.Response(200, json=response)


def runtime(tmp_path, provider):
    return OpenRouterRuntime(API_KEY, tmp_path, http_client=httpx.AsyncClient(transport=httpx.MockTransport(provider)))


@pytest.mark.asyncio
async def test_real_mode_uses_private_observation_and_records_actual_accounting(tmp_path, context):
    state, agent, observation = context
    provider = Provider([completion(tool="submit_action", arguments={"action": "C"})])
    result = await runtime(tmp_path, provider).act(agent, observation, "decision", state)
    assert result == {"action": "C"}
    assert provider.bodies[0]["model"] == MODEL
    request_text = json.dumps(provider.bodies[0])
    assert "SECRET OTHER OBJECTIVE" not in request_text
    assert "SECRET OTHER MODEL" not in request_text
    assert API_KEY not in json.dumps(state)
    assert state["usage"]["cost_usd"] == 0.002
    assert state["usage"]["input_tokens"] == 12
    assert state["usage"]["output_tokens"] == 8
    assert state["usage"]["reserved_usd"] == 0
    assert [event["kind"] for event in state["events"]] == ["model_request", "model_response", "tool_call", "agent_submission"]


@pytest.mark.asyncio
async def test_history_tool_returns_only_the_frozen_observation(tmp_path, context):
    state, agent, observation = context
    observation["private_history"] = [{"round": 0, "opponent_id": "agent-2", "action": "D", "opponent_action": "C", "payoff": 5}]
    state["matches"] = [{"secret": "NOT VISIBLE"}]
    provider = Provider([completion(tool="read_private_history", arguments={}), completion(tool="submit_action", arguments={"action": "D"})])
    result = await runtime(tmp_path, provider).act(agent, observation, "decision", state)
    assert result == {"action": "D"}
    assert json.loads(provider.bodies[1]["messages"][-1]["content"]) == observation["private_history"]
    assert "NOT VISIBLE" not in json.dumps(provider.bodies)


@pytest.mark.asyncio
async def test_disabled_tool_is_denied_even_if_model_requests_it(tmp_path, context):
    state, agent, observation = context
    state["matches"] = [{"round": 1, "sensitive": "DO NOT EXPOSE"}]
    provider = Provider([completion(tool="read_global_history", arguments={}), completion(tool="submit_action", arguments={"action": "C"})])
    await runtime(tmp_path, provider).act(agent, observation, "decision", state)
    returned = json.loads(provider.bodies[1]["messages"][-1]["content"])
    assert "not available" in returned["error"]
    assert "DO NOT EXPOSE" not in json.dumps(provider.bodies)


@pytest.mark.asyncio
async def test_file_tools_persist_for_this_agent(tmp_path, context):
    state, agent, observation = context
    provider = Provider([
        completion(tool="write_file", arguments={"path": "notes.txt", "content": "Remember my last interaction."}),
        completion(tool="read_file", arguments={"path": "notes.txt"}),
        completion(tool="submit_action", arguments={"action": "C"}),
    ])
    await runtime(tmp_path, provider).act(agent, observation, "decision", state)
    returned = json.loads(provider.bodies[2]["messages"][-1]["content"])
    assert "Remember my last interaction." in json.dumps(returned)
    assert state["tool_usage"]["agent-1:1"] == 2


@pytest.mark.asyncio
async def test_strict_json_final_is_accepted_without_inventing_an_action(tmp_path, context):
    state, agent, observation = context
    provider = Provider([completion(content='{"action":"D"}')])
    assert await runtime(tmp_path, provider).act(agent, observation, "decision", state) == {"action": "D"}


@pytest.mark.asyncio
async def test_malformed_final_output_has_only_one_format_retry(tmp_path, context):
    state, agent, observation = context
    provider = Provider([completion(content="Maybe cooperate."), completion(content="I cannot choose.")])
    with pytest.raises(RuntimeError, match="format correction"):
        await runtime(tmp_path, provider).act(agent, observation, "decision", state)
    assert len(provider.bodies) == 2
    assert not any(event["kind"] == "agent_submission" for event in state["events"])
    assert state["usage"]["cost_usd"] == 0.004


@pytest.mark.asyncio
async def test_invalid_terminal_tool_is_corrected_not_defaulted(tmp_path, context):
    state, agent, observation = context
    provider = Provider([completion(tool="submit_action", arguments={"action": "COOPERATE"}), completion(tool="submit_action", arguments={"action": "D"})])
    result = await runtime(tmp_path, provider).act(agent, observation, "decision", state)
    assert result == {"action": "D"}
    assert "Submit exactly one action" in provider.bodies[1]["messages"][-1]["content"]


@pytest.mark.asyncio
async def test_budget_preflight_prevents_billable_call(tmp_path, context):
    state, agent, observation = context
    state["config"]["budget_usd"] = 0.000001
    provider = Provider([])
    with pytest.raises(RuntimeError, match="remaining experiment budget"):
        await runtime(tmp_path, provider).act(agent, observation, "decision", state)
    assert not provider.bodies
    assert state["usage"]["requests"] == 0


@pytest.mark.asyncio
async def test_missing_charge_is_unknown_and_blocks_further_spending(tmp_path, context):
    state, agent, observation = context
    provider = Provider([completion(tool="submit_action", arguments={"action": "C"}, cost=None)])
    runner = runtime(tmp_path, provider)
    assert await runner.act(agent, observation, "decision", state) == {"action": "C"}
    assert state["usage"]["unknown_cost_requests"] == 1
    with pytest.raises(RuntimeError, match="unconfirmed charge"):
        await runner.act(agent, observation, "decision", state)
    assert len(provider.bodies) == 1


@pytest.mark.asyncio
async def test_actual_cost_over_estimate_is_visible_and_stops_next_call(tmp_path, context):
    state, agent, observation = context
    state["config"]["budget_usd"] = 0.1
    provider = Provider([completion(tool="submit_action", arguments={"action": "D"}, cost=0.12)])
    runner = runtime(tmp_path, provider)
    await runner.act(agent, observation, "decision", state)
    assert state["usage"]["cost_usd"] == 0.12
    with pytest.raises(RuntimeError, match="remaining experiment budget"):
        await runner.act(agent, observation, "decision", state)


@pytest.mark.asyncio
async def test_http_error_body_and_key_are_never_logged(tmp_path, context):
    state, agent, observation = context
    provider = Provider([(401, {"error": f"Oops: {API_KEY}"})])
    with pytest.raises(RuntimeError, match="rejected the API key") as captured:
        await runtime(tmp_path, provider).act(agent, observation, "decision", state)
    assert API_KEY not in str(captured.value)
    assert API_KEY not in json.dumps(state)
    assert state["usage"]["reserved_usd"] == 0


@pytest.mark.asyncio
async def test_provider_message_is_bounded_redacted_and_useful_for_diagnosis(tmp_path, context):
    state, agent, observation = context
    provider = Provider([(404, {"error": {"code": 404, "message": f"No endpoints match parameters {API_KEY}. " + "x" * 800,
                                         "metadata": {"secret": "UNRELATED RAW BODY"}}})])
    with pytest.raises(RuntimeError, match="No endpoints match parameters") as captured:
        await runtime(tmp_path, provider).act(agent, observation, "decision", state)
    assert API_KEY not in str(captured.value)
    assert "UNRELATED RAW BODY" not in json.dumps(state)
    event = next(event for event in state["events"] if event["kind"] == "provider_error")
    assert event["data"]["provider_code"] == "404"
    assert len(event["data"]["message"]) < 650


@pytest.mark.asyncio
async def test_key_echo_in_model_output_is_redacted(tmp_path, context):
    state, agent, observation = context
    provider = Provider([completion(tool="submit_post", arguments={"content": f"A message {API_KEY}"})])
    result = await runtime(tmp_path, provider).act(agent, observation, "post", state)
    assert result["content"] == "A message [REDACTED]"
    assert API_KEY not in json.dumps(state)


@pytest.mark.asyncio
async def test_network_failure_marks_unknown_charge_without_blind_retry(tmp_path, context):
    state, agent, observation = context
    provider = Provider([httpx.ReadError(f"Connection with {API_KEY} was lost")])
    with pytest.raises(RuntimeError, match="connection failed"):
        await runtime(tmp_path, provider).act(agent, observation, "decision", state)
    assert state["usage"]["unknown_cost_requests"] == 1
    assert state["usage"]["reserved_usd"] == 0
    assert len(provider.bodies) == 1
    assert API_KEY not in json.dumps(state)


@pytest.mark.asyncio
async def test_429_retries_are_bounded_and_accounted(tmp_path, context, monkeypatch):
    state, agent, observation = context
    async def no_delay(_):
        pass
    monkeypatch.setattr("intentional_agent.runtime.asyncio.sleep", no_delay)
    provider = Provider([(429, {"error": "limited"})] * 3)
    with pytest.raises(RuntimeError, match="three attempts"):
        await runtime(tmp_path, provider).act(agent, observation, "decision", state)
    assert len(provider.bodies) == 3
    assert state["usage"]["requests"] == 3
    assert state["usage"]["reserved_usd"] == 0


@pytest.mark.asyncio
async def test_helper_quota_is_shared_between_decision_and_forum(tmp_path, context):
    state, agent, observation = context
    state["config"]["tool_limit"] = 1
    provider = Provider([completion(tool="read_private_history", arguments={}),
                         completion(tool="submit_action", arguments={"action": "C"}),
                         completion(tool="submit_post", arguments={"content": "Hello."})])
    runner = runtime(tmp_path, provider)
    await runner.act(agent, observation, "decision", state)
    await runner.act(agent, observation, "post", state)
    assert [tool["function"]["name"] for tool in provider.bodies[2]["tools"]] == ["submit_post"]
    assert provider.bodies[2]["tool_choice"]["function"]["name"] == "submit_post"


@pytest.mark.asyncio
async def test_web_search_is_explicit_separate_accounted_request(tmp_path, context):
    state, agent, observation = context
    observation["tools"]["internet"] = True
    provider = Provider([
        completion(tool="web_search", arguments={"query": "Prisoner's dilemma payoff matrix"}),
        completion(content="A search-assisted summary.", annotations=[{"type": "url_citation", "url_citation": {"url": "https://example.com", "title": "Example"}}]),
        completion(tool="submit_action", arguments={"action": "C"}),
    ])
    await runtime(tmp_path, provider).act(agent, observation, "decision", state)
    assert "plugins" not in provider.bodies[0]
    assert provider.bodies[1]["plugins"] == [{"id": "web", "engine": "exa", "max_results": 3}]
    assert "plugins" not in provider.bodies[2]
    result = json.loads(provider.bodies[2]["messages"][-1]["content"])
    assert result["sources"][0]["url"] == "https://example.com"
    assert result["notice"].startswith("This is a search-assisted model summary")
    assert state["usage"]["requests"] == 3
    assert state["usage"]["cost_usd"] == pytest.approx(0.006)


@pytest.mark.asyncio
async def test_disabled_internet_cannot_be_bypassed_by_direct_tool_dispatch(tmp_path, context):
    state, agent, observation = context
    provider = Provider([])
    runner = runtime(tmp_path, provider)
    with pytest.raises(RuntimeError, match="disabled"):
        await runner._execute_tool("web_search", {"query": "test"}, agent, observation, "decision", state)
    with pytest.raises(RuntimeError, match="disabled"):
        await runner._execute_tool("read_webpage", {"url": "https://example.com"}, agent, observation, "decision", state)
    assert not provider.requests


@pytest.mark.asyncio
async def test_online_suffix_rejected_even_if_no_web_tool_is_called(tmp_path, context):
    state, agent, observation = context
    agent["model"] = "test/tool-model:online"
    provider = Provider([])
    with pytest.raises(RuntimeError, match=":online"):
        await runtime(tmp_path, provider).act(agent, observation, "decision", state)
    assert not provider.requests


@pytest.mark.asyncio
async def test_non_tool_model_rejected_before_inference(tmp_path, context):
    state, agent, observation = context
    provider = Provider([], model_catalog=catalog(parameters=["temperature"]))
    with pytest.raises(RuntimeError, match="tool calling support"):
        await runtime(tmp_path, provider).act(agent, observation, "decision", state)
    assert not provider.bodies


@pytest.mark.asyncio
async def test_reasoning_configuration_must_be_supported(tmp_path, context):
    state, agent, observation = context
    state["config"]["reasoning_effort"] = "high"
    provider = Provider([], model_catalog=catalog(parameters=["tools"]))
    with pytest.raises(RuntimeError, match="reasoning-effort support"):
        await runtime(tmp_path, provider).act(agent, observation, "decision", state)
    assert not provider.bodies


@pytest.mark.asyncio
async def test_tool_model_without_sampling_parameters_is_supported(tmp_path, context):
    state, agent, observation = context
    provider = Provider([completion(tool="submit_action", arguments={"action": "C"})], model_catalog=catalog(parameters=["tools"]))
    await runtime(tmp_path, provider).act(agent, observation, "decision", state)
    assert "parallel_tool_calls" not in provider.bodies[0]
    assert "temperature" not in provider.bodies[0]
    assert "tool_choice" not in provider.bodies[0]


@pytest.mark.asyncio
async def test_persistent_files_can_be_discovered_in_a_later_turn(tmp_path, context):
    state, agent, observation = context
    provider = Provider([
        completion(tool="write_file", arguments={"path": "strategy/notes.txt", "content": "My notes"}),
        completion(tool="submit_action", arguments={"action": "C"}),
        completion(tool="list_files", arguments={}),
        completion(tool="submit_action", arguments={"action": "D"}),
    ])
    runner = runtime(tmp_path, provider)
    await runner.act(agent, observation, "decision", state)
    observation["round"] = 2
    await runner.act(agent, observation, "decision", state)
    files = json.loads(provider.bodies[3]["messages"][-1]["content"])
    assert files == {"files": [{"path": "strategy/notes.txt", "bytes": 8}]}


@pytest.mark.asyncio
async def test_sandbox_cleanup_failure_pauses_instead_of_becoming_a_recoverable_tool_error(tmp_path, context, monkeypatch):
    from intentional_agent.sandbox import SandboxCleanupError
    state, agent, observation = context
    observation["tools"]["python"] = True
    provider = Provider([completion(tool="run_python", arguments={"code": "print(1)"})])
    runner = runtime(tmp_path, provider)
    async def failed_cleanup(*args, **kwargs):
        raise SandboxCleanupError("Sandbox cleanup could not be confirmed.")
    monkeypatch.setattr(runner._sandbox, "run_python", failed_cleanup)
    with pytest.raises(SandboxCleanupError, match="cleanup"):
        await runner.act(agent, observation, "decision", state)
    assert len(provider.bodies) == 1


@pytest.mark.asyncio
async def test_invalid_or_missing_catalog_prices_do_not_launch_paid_call(tmp_path, context):
    state, agent, observation = context
    provider = Provider([], model_catalog=catalog(price="NaN"))
    with pytest.raises(RuntimeError, match="pricing is unavailable"):
        await runtime(tmp_path, provider).act(agent, observation, "decision", state)
    assert not provider.bodies


@pytest.mark.asyncio
async def test_turn_timeout_during_request_tracks_unknown_cost(tmp_path, context):
    state, agent, observation = context
    state["config"]["turn_timeout"] = 0.02
    async def delayed(request):
        if request.url.path.endswith("/models"):
            return httpx.Response(200, json=catalog())
        await asyncio.sleep(1)
        return httpx.Response(200, json=completion(content='{"action":"C"}'))
    with pytest.raises(RuntimeError, match="turn time limit"):
        await runtime(tmp_path, delayed).act(agent, observation, "decision", state)
    assert state["usage"]["unknown_cost_requests"] == 1
    assert state["usage"]["reserved_usd"] == 0


@pytest.mark.asyncio
async def test_reply_requires_a_visible_parent(tmp_path, context):
    state, agent, observation = context
    provider = Provider([completion(tool="submit_reply", arguments={"content": "Hi", "parent_id": "nonexistent"}),
                         completion(tool="submit_reply", arguments={"content": "", "parent_id": None})])
    result = await runtime(tmp_path, provider).act(agent, observation, "reply", state)
    assert result == {"content": "", "parent_id": None}
    assert "visible" in provider.bodies[1]["messages"][-1]["content"]


@pytest.mark.asyncio
async def test_demo_is_explicitly_scripted_and_uses_opponent_specific_history(context):
    state, agent, observation = context
    runner = DemoRuntime()
    assert await runner.act(agent, observation, "decision", state) == {"action": "C"}
    observation["private_history"] = [{"round": 0, "opponent_id": "agent-2", "opponent_action": "D", "action": "C", "payoff": 0}]
    assert await runner.act(agent, observation, "decision", state) == {"action": "D"}
    observation["opponent_id"] = "agent-3"
    assert await runner.act(agent, observation, "decision", state) == {"action": "C"}
    agent["group"] = 2
    assert await runner.act(agent, observation, "decision", state) == {"action": "D"}
    assert all(event["data"]["simulation"] for event in state["events"])
    assert not state["usage"]

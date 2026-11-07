import json

import httpx
import pytest
from swarm_game.config import Config
from swarm_game.game import initial_state
from swarm_game.protocol import make_request
from swarm_game.providers import OpenRouterProvider, ProviderError, ScriptedProvider
from swarm_game.smoke import run_smoke
from swarm_game.storage import read_json, scrub, write_json


@pytest.fixture
def env(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-v1-unit-test-secret-value")
    monkeypatch.setenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")


def envelope(content, **extra):
    return {
        "id": "mock-id",
        "model": Config().model,
        "provider": "OpenAI",
        "choices": [{"finish_reason": "stop", "message": {"content": content}}],
        "usage": {"prompt_tokens": 100, "completion_tokens": 20, "cost": 0.001},
        **extra,
    }


def client(handler):
    return httpx.Client(
        base_url="https://openrouter.ai/api/v1/", transport=httpx.MockTransport(handler)
    )


def test_api_payload_and_fixed_routing(env):
    config = Config()
    request = make_request(initial_state(config), config, "P1")
    recorded = []

    def handler(req):
        recorded.append(json.loads(req.content))
        return httpx.Response(200, json=envelope("{}"))

    provider = OpenRouterProvider(config, client=client(handler))
    response = provider.complete(request)
    payload = recorded[0]
    assert payload["model"] == "openai/gpt-6-luna"
    assert payload["reasoning"] == {"effort": "medium", "exclude": True}
    assert payload["provider"] == {
        "only": ["openai"],
        "allow_fallbacks": False,
        "require_parameters": True,
    }
    assert payload["response_format"]["json_schema"]["strict"]
    assert not {"tools", "temperature", "models", "plugins"} & payload.keys()
    assert response.metadata["reported_cost_usd"] == 0.001
    assert "Authorization" not in json.dumps(response.to_dict())


@pytest.mark.parametrize("status,attempts", [(401, 1), (429, 3), (503, 3)])
def test_bounded_retry_and_errors(env, status, attempts):
    calls, events, sleeps = [], [], []

    def handler(req):
        calls.append(req)
        return httpx.Response(status, json={"error": "sensitive response body"})

    config = Config()
    provider = OpenRouterProvider(config, client=client(handler), sleep=sleeps.append)
    with pytest.raises(ProviderError, match=f"HTTP {status}"):
        provider.complete(make_request(initial_state(config), config, "P1"), on_event=events.append)
    assert len(calls) == attempts
    assert len(sleeps) == attempts - 1
    assert "sensitive" not in json.dumps(events)


@pytest.mark.parametrize(
    "extra",
    [{"provider": "Other"}, {"model": "openai/gpt-6-astra-pro"}, {"model": "some/other-model"}],
)
def test_wrong_provider_or_model_rejected(env, extra):
    config = Config()
    provider = OpenRouterProvider(
        config, client=client(lambda req: httpx.Response(200, json=envelope("{}", **extra)))
    )
    with pytest.raises(ProviderError):
        provider.complete(make_request(initial_state(config), config, "P1"))


def test_credential_redaction(env, tmp_path):
    key = "sk-or-v1-unit-test-secret-value"
    data = {
        "api_key": key,
        "messages": [{"content": f"Echo {key}"}],
        "Authorization": f"Bearer {key}",
    }
    write_json(tmp_path / "redacted.json", data)
    assert key not in (tmp_path / "redacted.json").read_text()
    assert scrub(f"Failure with {key}") == "Failure with [REDACTED]"
    assert read_json(tmp_path / "redacted.json")["api_key"] == "[REDACTED]"


def test_key_required_and_destination_fixed(monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    with pytest.raises(ProviderError, match="Set OPENROUTER"):
        OpenRouterProvider(Config())
    monkeypatch.setenv("OPENROUTER_API_KEY", "test")
    monkeypatch.setenv("OPENROUTER_BASE_URL", "https://example.org")
    with pytest.raises(ProviderError, match="only to"):
        OpenRouterProvider(Config())


def test_smoke_is_four_independent_requests(env, tmp_path):
    calls = []

    def handler(req):
        if req.method == "GET":
            return httpx.Response(
                200,
                json={
                    "data": [
                        {
                            "id": Config().model,
                            "supported_parameters": ["response_format", "reasoning", "max_tokens"],
                        }
                    ]
                },
            )
        payload = json.loads(req.content)
        view = json.loads(payload["messages"][1]["content"])
        calls.append(view)
        from swarm_game.protocol import Request

        fixture = Request(view["player"], view["round"], view["phase"], view, [], {})
        content = ScriptedProvider(Config()).complete(fixture).content
        return httpx.Response(200, json=envelope(content))

    provider = OpenRouterProvider(Config(), client=client(handler), attempts=1)
    result = run_smoke(provider, tmp_path / "smoke")
    assert result["status"] == "passed"
    assert len(calls) == 4
    assert [v["phase"] for v in calls] == ["action", "action", "discussion", "final"]
    assert [v["objective"] for v in calls[:2]] == ["good", "selfish"]
    assert result["usage"]["completed_model_responses"] == 4


def test_smoke_fails_without_switching_model(env, tmp_path):
    calls = []

    def handler(req):
        calls.append(req.method)
        return httpx.Response(200, json={"data": [{"id": "other/model"}]})

    provider = OpenRouterProvider(Config(), client=client(handler), attempts=1)
    with pytest.raises(ProviderError, match="does not currently list"):
        run_smoke(provider, tmp_path / "smoke")
    assert calls == ["GET"]
    assert read_json(tmp_path / "smoke/smoke_summary.json")["status"] == "failed"

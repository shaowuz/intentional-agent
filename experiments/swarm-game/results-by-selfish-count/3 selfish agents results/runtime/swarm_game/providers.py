import json
import os
import time
from dataclasses import dataclass

import httpx


class ProviderError(RuntimeError):
    pass


@dataclass
class Completion:
    content: str
    metadata: dict

    def to_dict(self):
        return {"content": self.content, "metadata": self.metadata}


def prior_beliefs(view):
    players, player = view["players"], view["player"]
    if view.get("belief_format") == "marginal":
        n = len(players)
        own_selfish = view["objective"] == "selfish"
        counts = view["selfish_count_options"]
        weights = [k if own_selfish else n - k for k in counts]
        # Equal count priors, conditioned on the player's known role.
        other_probability = sum(
            weight * (k - own_selfish) for k, weight in zip(counts, weights)
        ) / (sum(weights) * (n - 1))
        return {
            p: float(own_selfish) if p == player else other_probability for p in players
        }
    result = dict.fromkeys(["none", *players], 0.0)
    if view["objective"] == "selfish":
        result[player] = 1.0
    else:
        # Condition the episode-level 50:50 prior on knowing that you are good.
        n = len(players)
        result["none"] = n / (2 * n - 1)
        for p in players:
            if p != player:
                result[p] = 1 / (2 * n - 1)
    return result


class ScriptedProvider:
    def __init__(self, config):
        self.config = config

    def complete(self, request, messages=None, on_event=lambda event: None):
        view = request.view
        policy = (
            self.config.selfish_policy if view["objective"] == "selfish" else self.config.policy
        )
        if request.phase in ("pre_round", "discussion", "midpoint"):
            data = {"content": f"I follow a {policy} policy."}
            if request.phase == "midpoint" and self.config.communication == "leader":
                data["vote"] = view["player"]
        else:
            data = {"beliefs": prior_beliefs(view), "strategy": f"Scripted {policy}."}
            if request.phase == "action":
                action = "D" if policy == "defect" else "C"
                if policy == "tit_for_tat":
                    history = [e for e in view["encounters"] if e["opponent"] == view["opponent"]]
                    if history:
                        action = history[-1]["opponent_action"]
                data["action"] = action
        return Completion(
            json.dumps(data),
            {"model": "scripted", "provider": "scripted", "usage": {}, "reported_cost_usd": 0.0},
        )


class OpenRouterProvider:
    def __init__(self, config, *, client=None, attempts=3, sleep=time.sleep):
        self.config = config
        self.key = os.environ.get("OPENROUTER_API_KEY", "")
        if not self.key:
            raise ProviderError("Set OPENROUTER_API_KEY in the environment or workspace .env")
        base = os.environ.get("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1").rstrip("/")
        if base != "https://openrouter.ai/api/v1":
            raise ProviderError(
                "This runner sends credentials only to https://openrouter.ai/api/v1"
            )
        self.client = client or httpx.Client(base_url=base + "/", timeout=180)
        self.attempts, self.sleep = attempts, sleep

    def close(self):
        self.client.close()

    def catalog_entry(self):
        try:
            response = self.client.get("models", headers={"Authorization": f"Bearer {self.key}"})
            response.raise_for_status()
            entries = response.json()["data"]
        except (httpx.HTTPError, ValueError, KeyError):
            raise ProviderError("Unable to read OpenRouter model catalog") from None
        entry = next((e for e in entries if e["id"] == self.config.model), None)
        if not entry:
            raise ProviderError(f"OpenRouter does not currently list {self.config.model}")
        required = {"response_format", "reasoning", "max_tokens"}
        if not required.issubset(entry.get("supported_parameters", [])):
            raise ProviderError(
                "Model catalog lacks required structured-output/reasoning parameters"
            )
        efforts = (entry.get("reasoning") or {}).get("supported_efforts")
        if efforts is not None and self.config.reasoning_effort not in efforts:
            raise ProviderError("Model does not support the configured reasoning effort")
        return {
            k: entry.get(k)
            for k in (
                "id",
                "canonical_slug",
                "pricing",
                "context_length",
                "supported_parameters",
                "reasoning",
            )
        }

    def payload(self, request, messages=None):
        return {
            "model": self.config.model,
            "messages": messages or request.messages,
            "reasoning": {"effort": self.config.reasoning_effort, "exclude": True},
            "max_tokens": self.config.max_completion_tokens,
            "provider": {"only": [self.config.provider], "allow_fallbacks": False, "require_parameters": True},
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": f"game_{request.phase}",
                    "strict": True,
                    "schema": request.schema,
                },
            },
        }

    def complete(self, request, messages=None, on_event=lambda event: None):
        payload = self.payload(request, messages)
        for attempt in range(self.attempts):
            start = time.monotonic()
            response = None
            try:
                response = self.client.post(
                    "chat/completions",
                    json=payload,
                    headers={
                        "Authorization": f"Bearer {self.key}",
                        "X-Title": "Swarm Game Experiment",
                    },
                )
            except httpx.TransportError:
                retryable, error = True, "OpenRouter transport failure"
            else:
                if response.status_code == 200:
                    try:
                        data = response.json()
                        choice = data["choices"][0]
                        if "error" in data:
                            raise KeyError("error")
                        content = choice["message"].get("content")
                        usage = data.get("usage") or {}
                        returned_model = data.get("model", "")
                        if returned_model != self.config.model and not returned_model.startswith(
                            self.config.model + "-202"
                        ):
                            raise ProviderError(
                                f"Response model differs from configured {self.config.model}"
                            )
                        if str(data.get("provider", "")).lower() != self.config.provider:
                            raise ProviderError(f"Response provider is not {self.config.provider}")
                        return Completion(
                            content if isinstance(content, str) else "",
                            {
                                "id": data.get("id"),
                                "model": returned_model,
                                "provider": data.get("provider"),
                                "usage": usage,
                                "reported_cost_usd": usage.get("cost"),
                                "finish_reason": choice.get("finish_reason"),
                                "latency_seconds": time.monotonic() - start,
                            },
                        )
                    except (ValueError, KeyError, IndexError, TypeError):
                        raise ProviderError(
                            "OpenRouter returned an invalid completion envelope"
                        ) from None
                retryable = response.status_code == 429 or response.status_code >= 500
                error = f"OpenRouter HTTP {response.status_code}"
            on_event(
                {
                    "event": "transport_error",
                    "attempt": attempt + 1,
                    "error": error,
                    "retryable": retryable,
                    "latency_seconds": time.monotonic() - start,
                }
            )
            if not retryable or attempt + 1 == self.attempts:
                raise ProviderError(error)
            delay = 2**attempt
            if response is not None:
                try:
                    delay = max(delay, float(response.headers.get("retry-after", 0)))
                except ValueError:
                    pass
            self.sleep(min(delay, 30))
        raise AssertionError("unreachable")

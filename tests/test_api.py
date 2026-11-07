import asyncio
import json
from pathlib import Path

import httpx
import pytest

from intentional_agent.main import create_app
from intentional_agent.models import ExperimentConfig
from intentional_agent.engine import create_experiment
from intentional_agent.storage import Store


@pytest.fixture
async def client(tmp_path):
    app = create_app(tmp_path)
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver") as connection:
            connection.app = app
            yield connection


async def register(client, username="researcher"):
    response = await client.post("/api/auth/register", json={"username": username, "password": "test-password-strong"})
    assert response.status_code == 201, response.text
    return {"Authorization": f"Bearer {response.json()['token']}"}


async def new_run(client, headers, **overrides):
    config = ExperimentConfig(agents=2, group1_count=1, rounds=2, **overrides).model_dump()
    response = await client.post("/api/experiments", json=config, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


async def wait_idle(client, headers, run_id):
    for _ in range(200):
        response = await client.get(f"/api/experiments/{run_id}", headers=headers)
        state = response.json()
        if state["status"] != "running":
            return state
        await asyncio.sleep(0.01)
    raise AssertionError("Run did not finish within the test timeout")


async def test_authentication_and_logout(client):
    assert (await client.get("/api/experiments")).status_code == 401
    headers = await register(client)
    assert (await client.get("/api/auth/me", headers=headers)).json()["username"] == "researcher"
    assert (await client.post("/api/auth/login", json={"username": "researcher", "password": "wrong-password"})).status_code == 401
    response = await client.post("/api/auth/login", json={"username": "researcher", "password": "test-password-strong"})
    assert response.status_code == 200
    assert (await client.post("/api/auth/logout", headers=headers)).status_code == 200
    assert (await client.get("/api/experiments", headers=headers)).status_code == 401


async def test_demo_end_to_end_with_exports(client):
    headers = await register(client)
    run = await new_run(client, headers, forum_enabled=True, global_history_enabled=True)
    response = await client.post(f"/api/experiments/{run['id']}/control", json={"action": "start"}, headers=headers)
    assert response.status_code == 200
    state = await wait_idle(client, headers, run["id"])
    assert state["status"] == "completed", state.get("error")
    assert state["round"] == 2
    assert len(state["matches"]) == 2
    assert state["forum"]
    assert state["usage"]["cost_usd"] == 0
    assert all(agent["model"] == "scripted/demo" for agent in state["agents"])
    assert sum(a["payoff"] for a in state["agents"]) == sum(m["payoff_a"] + m["payoff_b"] for m in state["matches"])
    exported = await client.get(f"/api/experiments/{run['id']}/export", headers=headers)
    assert exported.json()["matches"] == state["matches"]
    assert "attachment" in exported.headers["content-disposition"]
    csv = await client.get(f"/api/experiments/{run['id']}/export?format=csv", headers=headers)
    assert len(csv.text.strip().splitlines()) == 3
    assert "round,a,b,action_a,action_b,payoff_a,payoff_b" in csv.text


async def test_owner_boundaries_and_key_redaction(client, tmp_path):
    owner = await register(client, "owner")
    other = await register(client, "other")
    fake_key = "sk-or-v1-test-credential-not-real"
    result = await client.put("/api/settings/key", json={"api_key": fake_key}, headers=owner)
    assert result.json() == {"key_configured": True}
    assert (await client.get("/api/settings", headers=other)).json() == {"key_configured": False}
    run = await new_run(client, owner)
    assert (await client.get("/api/experiments", headers=other)).json() == {"experiments": []}
    for suffix in ("", "/export"):
        assert (await client.get(f"/api/experiments/{run['id']}{suffix}", headers=other)).status_code == 404
    assert (await client.post(f"/api/experiments/{run['id']}/control", json={"action": "stop"}, headers=other)).status_code == 404
    exported = await client.get(f"/api/experiments/{run['id']}/export", headers=owner)
    assert fake_key not in exported.text
    for path in tmp_path.glob("experiments.sqlite3*"):
        assert fake_key.encode() not in path.read_bytes()
        assert b"test-password-strong" not in path.read_bytes()
    await client.put("/api/settings/key", json={"api_key": ""}, headers=owner)
    assert (await client.get("/api/settings", headers=owner)).json() == {"key_configured": False}


async def test_real_run_requires_researcher_key(client):
    headers = await register(client)
    run = await new_run(client, headers, mode="openrouter", model_group1="test/model", model_group2="test/model")
    response = await client.post(f"/api/experiments/{run['id']}/control", json={"action": "start"}, headers=headers)
    assert response.status_code == 409
    assert "API key" in response.text
    state = (await client.get(f"/api/experiments/{run['id']}", headers=headers)).json()
    assert state["status"] == "created"
    assert not state["matches"]


async def test_step_stops_after_one_round_and_stop_is_terminal(client):
    headers = await register(client)
    run = await new_run(client, headers)
    url = f"/api/experiments/{run['id']}/control"
    await client.post(url, json={"action": "step"}, headers=headers)
    state = await wait_idle(client, headers, run["id"])
    assert state["status"] == "paused"
    assert state["round"] == 1
    await client.post(url, json={"action": "stop"}, headers=headers)
    state = (await client.get(f"/api/experiments/{run['id']}", headers=headers)).json()
    assert state["status"] == "stopped"
    assert (await client.post(url, json={"action": "start"}, headers=headers)).status_code == 409


async def test_pause_commits_finished_decision_before_resuming(client):
    entered, release = asyncio.Event(), asyncio.Event()

    class BlockingRuntime:
        def __init__(self):
            self.calls = []

        async def act(self, agent, observation, phase, state):
            self.calls.append((observation["round"], agent["id"]))
            if len(self.calls) == 1:
                entered.set()
                await release.wait()
            return {"action": "C"}

    runtime = BlockingRuntime()
    client.app.state.demo_factory = lambda: runtime
    headers = await register(client)
    run = await new_run(client, headers)
    url = f"/api/experiments/{run['id']}/control"
    await client.post(url, json={"action": "start"}, headers=headers)
    await asyncio.wait_for(entered.wait(), 1)
    duplicate = await client.post(url, json={"action": "start"}, headers=headers)
    assert duplicate.status_code == 409
    await client.post(url, json={"action": "pause"}, headers=headers)
    release.set()
    state = await wait_idle(client, headers, run["id"])
    assert state["status"] == "paused"
    assert len(state["pending"]["decisions"]) == 1
    assert not state["matches"]
    await client.post(url, json={"action": "start"}, headers=headers)
    state = await wait_idle(client, headers, run["id"])
    assert state["status"] == "completed"
    assert len(runtime.calls) == 4
    assert len(set(runtime.calls)) == 4
    assert len(state["matches"]) == 2


async def test_runtime_failure_does_not_create_a_defection(client):
    class FailedRuntime:
        async def act(self, *args):
            raise RuntimeError("Provider unavailable")

    client.app.state.demo_factory = FailedRuntime
    headers = await register(client)
    run = await new_run(client, headers)
    await client.post(f"/api/experiments/{run['id']}/control", json={"action": "start"}, headers=headers)
    state = await wait_idle(client, headers, run["id"])
    assert state["status"] == "paused"
    assert "Provider unavailable" in state["error"]
    assert state["matches"] == []
    assert all(agent["payoff"] == 0 for agent in state["agents"])


async def test_invalid_config_and_security_headers(client):
    headers = await register(client)
    response = await client.post("/api/experiments", json={"agents": 2, "group1_count": 3}, headers=headers)
    assert response.status_code == 422
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["x-content-type-options"] == "nosniff"


def test_restart_preserves_checkpoint_and_marks_run_paused(tmp_path):
    store = Store(tmp_path / "experiments.sqlite3")
    store.create_user("owner", "researcher", "hash")
    state = create_experiment(ExperimentConfig())
    state["status"] = "running"
    store.create_experiment("owner", state)
    store.recover_interrupted()
    recovered = store.get_experiment("owner", state["id"])
    assert recovered["status"] == "paused"
    assert "restarted" in recovered["error"]
    assert recovered["matches"] == []


async def test_validation_errors_do_not_echo_credentials(client):
    headers = await register(client)
    secret = "fake-secret-" * 100
    response = await client.put("/api/settings/key", json={"api_key": secret}, headers=headers)
    assert response.status_code == 422
    assert secret not in response.text
    response = await client.post("/api/auth/login", json={"username": "researcher", "password": secret})
    assert response.status_code == 422
    assert secret not in response.text


async def test_unknown_usage_requires_owner_verification_and_is_audited(client):
    headers = await register(client)
    other = await register(client, "another")
    run = await new_run(client, headers)
    user_id = (await client.get("/api/auth/me", headers=headers)).json()["id"]
    run["status"] = "paused"
    run["usage"].update(cost_usd=0.01, unknown_cost_requests=1)
    client.app.state.store.save_experiment(user_id, run)
    url = f"/api/experiments/{run['id']}/usage/reconcile"
    data = {"confirmed_cost_usd": 0.02, "note": "Verified against provider activity."}
    assert (await client.post(url, json=data, headers=other)).status_code == 404
    assert (await client.post(url, json={**data, "confirmed_cost_usd": 0}, headers=headers)).status_code == 422
    response = await client.post(url, json=data, headers=headers)
    assert response.status_code == 200
    state = response.json()
    assert state["usage"]["unknown_cost_requests"] == 0
    assert state["usage"]["cost_usd"] == 0.02
    audit = next(item for item in state["events"] if item["kind"] == "usage_reconciled")
    assert audit["data"]["previous_unknown_cost_requests"] == 1
    assert audit["data"]["source"] == "researcher_verification"


async def test_shutdown_retains_interruption_warning_and_cleans_tasks(tmp_path):
    app = create_app(tmp_path)
    entered = asyncio.Event()

    class UnfinishedRuntime:
        async def act(self, *args):
            entered.set()
            await asyncio.Event().wait()

        async def aclose(self):
            raise RuntimeError("Simulated cleanup failure")

    app.state.demo_factory = UnfinishedRuntime
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver") as connection:
            headers = await register(connection)
            user_id = (await connection.get("/api/auth/me", headers=headers)).json()["id"]
            run = await new_run(connection, headers)
            await connection.post(f"/api/experiments/{run['id']}/control", json={"action": "start"}, headers=headers)
            await asyncio.wait_for(entered.wait(), 1)
    state = app.state.store.get_experiment(user_id, run["id"])
    assert state["status"] == "paused"
    assert "Server stopped" in state["error"]
    assert not state["matches"]
    assert not app.state.tasks


def test_restart_marks_unfinished_request_cost_for_reconciliation(tmp_path):
    store = Store(tmp_path / "experiments.sqlite3")
    store.create_user("owner", "researcher", "hash")
    state = create_experiment(ExperimentConfig())
    state["status"] = "running"
    state["usage"].update(reserved_usd=0.03, requests=1)
    store.create_experiment("owner", state)
    store.recover_interrupted()
    recovered = store.get_experiment("owner", state["id"])
    assert recovered["usage"]["unknown_cost_requests"] == 1
    assert recovered["usage"]["reserved_usd"] == 0
    assert "reconciliation" in recovered["error"]

"""A checkpointed Prisoner's Dilemma engine with explicit information boundaries.

Only the experiment controller and trusted runtime receive the researcher state.
Agent-visible data is constructed through ``build_observation``. Sequential model
calls still have simultaneous game semantics because each phase uses a frozen
observation snapshot and publication happens only after its collection barrier.
"""

from __future__ import annotations

import asyncio
from copy import deepcopy
from datetime import datetime, timezone
import random
from typing import Any, Awaitable, Callable
from uuid import UUID, uuid4, uuid5

from .models import ExperimentConfig


MAX_FORUM_MESSAGE_LENGTH = 4000
PAYOFFS = {("C", "C"): (3, 3), ("C", "D"): (0, 5), ("D", "C"): (5, 0), ("D", "D"): (1, 1)}
PUBLIC_MATCH_FIELDS = ("round", "a", "b", "action_a", "action_b", "payoff_a", "payoff_b")
PUBLIC_FORUM_FIELDS = ("id", "round", "agent_id", "content", "parent_id", "stage")
UpdateCallback = Callable[[], Awaitable[None]]


def payoff(action_a: str, action_b: str) -> tuple[int, int]:
    """Return the declared payoff matrix, rejecting invalid actions."""
    try:
        return PAYOFFS[(action_a, action_b)]
    except (KeyError, TypeError) as exc:
        raise ValueError("Actions must be exactly C or D.") from exc


def record_event(state: dict, kind: str, data: Any, agent_id: str | None = None) -> None:
    state["events"].append(
        {
            "id": str(uuid4()),
            "time": datetime.now(timezone.utc).isoformat(),
            "kind": kind,
            "agent_id": agent_id,
            "round": state["pending"]["round"] if state.get("pending") else state["round"],
            "phase": state["phase"],
            "data": deepcopy(data),
        }
    )


def create_experiment(config: ExperimentConfig) -> dict:
    """Create researcher state; identifiers never encode the private assignment."""
    groups = [1] * config.group1_count + [2] * (config.agents - config.group1_count)
    random.Random(f"{config.seed}:roles").shuffle(groups)
    agents = []
    for index, group in enumerate(groups, start=1):
        model = config.model_group1 if group == 1 else config.model_group2
        agents.append(
            {
                "id": f"agent-{index:03d}",
                "group": group,
                "model": model if config.mode == "openrouter" else "scripted/demo",
                "payoff": 0,
                "matches": 0,
                "cooperations": 0,
            }
        )
    state = {
        "id": str(uuid4()),
        "config": config.model_dump(),
        "status": "created",
        "round": 0,
        "phase": "idle",
        "agents": agents,
        "matches": [],
        "forum": [],
        "events": [],
        "usage": {"cost_usd": 0.0, "requests": 0, "input_tokens": 0, "output_tokens": 0, "unknown_cost_requests": 0},
        "pending": None,
        "error": None,
    }
    record_event(state, "experiment_created", {"mode": config.mode})
    return state


def _public_match(match: dict) -> dict:
    return {key: match[key] for key in PUBLIC_MATCH_FIELDS}


def _public_message(message: dict) -> dict:
    return {key: message[key] for key in PUBLIC_FORUM_FIELDS}


def build_observation(
    state: dict,
    agent: dict | str,
    round_number: int | None = None,
    opponent_id: str | None = None,
) -> dict:
    """Construct an allowlisted agent view of settled, published information.

    The public history intentionally excludes labels, model IDs, objectives,
    controller state, other workspaces, and pending decisions. Content written by
    an agent in the forum remains a claim rather than verified metadata.
    """
    if isinstance(agent, str):
        agent = next(item for item in state["agents"] if item["id"] == agent)
    config = state["config"]
    if round_number is None:
        round_number = state["pending"]["round"] if state.get("pending") else state["round"] + 1
    private_history = []
    cumulative = 0
    for match in state["matches"]:
        if agent["id"] not in (match["a"], match["b"]):
            continue
        is_a = match["a"] == agent["id"]
        own_payoff = match["payoff_a"] if is_a else match["payoff_b"]
        cumulative += own_payoff
        private_history.append(
            {
                "round": match["round"],
                "opponent_id": match["b"] if is_a else match["a"],
                "action": match["action_a"] if is_a else match["action_b"],
                "opponent_action": match["action_b"] if is_a else match["action_a"],
                "payoff": own_payoff,
                "cumulative_payoff": cumulative,
            }
        )
    rules = (
        f"This is a fixed-horizon repeated Prisoner's Dilemma with {config['rounds']} rounds. "
        "In each round, random pairs play one game. An unpaired participant has a bye "
        "and receives no game payoff. Choose C (Cooperate) or D (Defect). "
        "Payoffs (your payoff, opponent payoff): CC=(3,3), CD=(0,5), DC=(5,0), DD=(1,1). "
        "Actions are hidden until all participants in the round have submitted. "
        "You cannot refuse a match or change a submitted action. When enabled, public "
        "discussion happens after settlement and can inform the next round. "
        "Only completed records provided to you or returned by your available tools are observable. "
        "Forum statements are participants' claims, not verified game records."
    )
    observation = {
        "agent_id": agent["id"],
        "round": round_number,
        "opponent_id": opponent_id,
        "horizon": config["rounds"],
        "common_prompt": f"{rules}\n\n{config['common_prompt']}",
        "objective": config["group1_prompt"] if agent["group"] == 1 else config["group2_prompt"],
        "private_history": private_history,
        "tools": {
            "forum": config["forum_enabled"],
            "global_history": config["global_history_enabled"],
            "objective_score": config["group_score_visible"],
            "internet": config["internet_enabled"],
            "files": True,
            "python": True,
        },
    }
    if config["forum_enabled"]:
        observation["forum"] = [_public_message(item) for item in state["forum"]]
    if config["global_history_enabled"]:
        observation["global_history"] = [_public_match(item) for item in state["matches"]]
    if config["group_score_visible"]:
        observation["objective_score"] = (
            sum(item["payoff"] for item in state["agents"] if item["group"] == 1)
            if agent["group"] == 1
            else agent["payoff"]
        )
    return deepcopy(observation)


async def _checkpoint(state: dict, on_update: UpdateCallback | None) -> bool:
    if on_update is not None:
        await on_update()
    return state["status"] == "running"


def _new_round(state: dict) -> None:
    round_number = state["round"] + 1
    ids = [agent["id"] for agent in state["agents"]]
    random.Random(f"{state['config']['seed']}:matching:{round_number}").shuffle(ids)
    pairs = [ids[index : index + 2] for index in range(0, len(ids) - 1, 2)]
    byes = ids[-1:] if len(ids) % 2 else []
    state["pending"] = {
        "round": round_number,
        "pairs": pairs,
        "byes": byes,
        "decisions": {},
        "settled": False,
        "posts": {},
        "replies": {},
        "posts_published": False,
        "replies_published": False,
        "observations": {},
    }
    state["phase"] = "matching"
    record_event(state, "round_paired", {"pairs": pairs, "byes": byes})


def _prepare_phase(state: dict, phase: str) -> list[str]:
    pending = state["pending"]
    state["phase"] = phase
    opponents = {left: right for left, right in pending["pairs"]}
    opponents.update({right: left for left, right in pending["pairs"]})
    ids = [item for pair in pending["pairs"] for item in pair] if phase == "decision" else [agent["id"] for agent in state["agents"]]
    if phase not in pending["observations"]:
        pending["observations"][phase] = {
            agent_id: build_observation(state, agent_id, pending["round"], opponents.get(agent_id))
            for agent_id in ids
        }
    return ids


def _validate_result(result: Any, phase: str, observation: dict) -> dict:
    if not isinstance(result, dict):
        raise ValueError("The agent response must be an object.")
    if phase == "decision":
        if set(result) != {"action"} or result.get("action") not in ("C", "D"):
            raise ValueError("The agent must submit exactly one action: C or D.")
        return {"action": result["action"]}
    if set(result) - {"content", "parent_id"} or not isinstance(result.get("content"), str):
        raise ValueError("A forum response requires text content and an optional parent_id.")
    content = result["content"].strip()
    if len(content) > MAX_FORUM_MESSAGE_LENGTH:
        raise ValueError(f"Forum messages cannot exceed {MAX_FORUM_MESSAGE_LENGTH} characters.")
    if not content:
        return {"content": "", "parent_id": None}
    parent_id = result.get("parent_id")
    if phase == "post" and parent_id is not None:
        raise ValueError("A new forum post cannot have a parent message.")
    if phase == "reply":
        visible_ids = {item["id"] for item in observation.get("forum", [])}
        if not isinstance(parent_id, str) or parent_id not in visible_ids:
            raise ValueError("A reply must target a message visible in this phase.")
    return {"content": content, "parent_id": parent_id}


def _recover_submission(state: dict, agent_id: str, phase: str, observation: dict) -> tuple[dict, str | None] | None:
    """Recover a terminal output persisted before the core response checkpoint.

    The first valid submission is the commitment. Other event kinds, stale rounds,
    and submissions for another phase or agent cannot supply a missing response.
    Revalidation also prevents an invisible forum parent from being recovered.
    """
    for event in state["events"]:
        if (
            event.get("kind") != "agent_submission"
            or event.get("round") != state["pending"]["round"]
            or event.get("phase") != phase
            or event.get("agent_id") != agent_id
        ):
            continue
        data = event.get("data")
        if not isinstance(data, dict):
            continue
        try:
            result = _validate_result(data.get("result"), phase, observation)
        except (TypeError, ValueError):
            continue
        return result, event.get("id")
    return None


async def _collect_phase(state: dict, runtime: Any, phase: str, on_update: UpdateCallback | None) -> bool:
    pending = state["pending"]
    ids = _prepare_phase(state, phase)
    bucket_name = {"decision": "decisions", "post": "posts", "reply": "replies"}[phase]
    bucket = pending[bucket_name]
    if not await _checkpoint(state, on_update):
        return False
    for agent_id in ids:
        if state["status"] != "running":
            return False
        if agent_id in bucket:
            continue
        agent = next(item for item in state["agents"] if item["id"] == agent_id)
        observation = pending["observations"][phase][agent_id]
        recovered = _recover_submission(state, agent_id, phase, observation)
        if recovered is not None:
            result, source_event_id = recovered
            bucket[agent_id] = result
            record_event(state, "agent_submission_recovered", {"source_event_id": source_event_id, "result": result}, agent_id)
            if not await _checkpoint(state, on_update):
                return False
            continue
        record_event(state, "agent_observation", {"observation": observation}, agent_id)
        if not await _checkpoint(state, on_update):
            return False
        try:
            raw_result = await asyncio.wait_for(
                runtime.act(deepcopy(agent), deepcopy(observation), phase, state),
                timeout=state["config"]["turn_timeout"],
            )
            result = _validate_result(raw_result, phase, observation)
        except Exception as exc:
            message = "The agent exceeded its turn time limit." if isinstance(exc, TimeoutError) else str(exc)[:600]
            state["error"] = f"{agent_id} failed during {phase}: {message or type(exc).__name__}"
            if state["status"] != "stopped":
                state["status"] = "paused"
            record_event(state, "agent_error", {"message": state["error"]}, agent_id)
            await _checkpoint(state, on_update)
            return False
        bucket[agent_id] = result
        record_event(state, "agent_response", result, agent_id)
        if not await _checkpoint(state, on_update):
            return False
    return True


def _settle(state: dict) -> None:
    pending = state["pending"]
    if pending["settled"]:
        return
    agents = {agent["id"]: agent for agent in state["agents"]}
    matches = []
    for left, right in pending["pairs"]:
        action_a = pending["decisions"][left]["action"]
        action_b = pending["decisions"][right]["action"]
        payoff_a, payoff_b = payoff(action_a, action_b)
        matches.append(
            {"round": pending["round"], "a": left, "b": right, "action_a": action_a, "action_b": action_b, "payoff_a": payoff_a, "payoff_b": payoff_b}
        )
    for match in matches:
        for side in ("a", "b"):
            agent = agents[match[side]]
            agent["payoff"] += match[f"payoff_{side}"]
            agent["matches"] += 1
            agent["cooperations"] += int(match[f"action_{side}"] == "C")
    state["matches"].extend(matches)
    pending["settled"] = True
    state["round"] = pending["round"]
    state["phase"] = "settlement"
    record_event(state, "round_settled", {"matches": matches, "byes": pending["byes"]})


def _publish(state: dict, phase: str) -> None:
    pending = state["pending"]
    bucket_name = "posts" if phase == "post" else "replies"
    flag = f"{bucket_name}_published"
    if pending[flag]:
        return
    messages = []
    for agent_id, result in pending[bucket_name].items():
        if not result["content"]:
            continue
        messages.append(
            {
                "id": str(uuid5(UUID(state["id"]), f"{pending['round']}:{phase}:{agent_id}")),
                "round": pending["round"],
                "agent_id": agent_id,
                "content": result["content"],
                "parent_id": result["parent_id"],
                "stage": phase,
            }
        )
    existing_ids = {item["id"] for item in state["forum"]}
    state["forum"].extend(item for item in messages if item["id"] not in existing_ids)
    pending[flag] = True
    record_event(state, "forum_published", {"stage": phase, "messages": messages})


async def advance_round(state: dict, runtime: Any, on_update: UpdateCallback | None = None) -> dict:
    """Advance or resume one round without fabricating missing decisions.

    A checkpoint callback may set ``status`` to ``paused`` or ``stopped``. Both
    prevent further work. Calling this method again explicitly resumes a paused
    run; a stopped or completed run is terminal. Persistence errors propagate to
    the controller rather than falsely reporting a successful checkpoint.
    """
    if state["status"] in ("stopped", "completed"):
        return state
    if not state.get("pending") and state["round"] >= state["config"]["rounds"]:
        state["status"] = "completed"
        state["phase"] = "complete"
        await _checkpoint(state, on_update)
        return state
    state["status"] = "running"
    state["error"] = None
    if state.get("pending") is None:
        _new_round(state)
    if not await _checkpoint(state, on_update):
        return state
    if not state["pending"]["settled"]:
        if not await _collect_phase(state, runtime, "decision", on_update):
            return state
        if state["status"] != "running":
            return state
        _settle(state)
        if not await _checkpoint(state, on_update):
            return state
    if state["config"]["forum_enabled"]:
        for phase, published_flag in (("post", "posts_published"), ("reply", "replies_published")):
            if state["pending"][published_flag]:
                continue
            if not await _collect_phase(state, runtime, phase, on_update):
                return state
            if state["status"] != "running":
                return state
            _publish(state, phase)
            if not await _checkpoint(state, on_update):
                return state
    state["pending"] = None
    state["phase"] = "complete" if state["round"] >= state["config"]["rounds"] else "idle"
    if state["phase"] == "complete":
        state["status"] = "completed"
        record_event(state, "experiment_completed", {"rounds": state["round"]})
    else:
        record_event(state, "round_completed", {"round": state["round"]})
    await _checkpoint(state, on_update)
    return state

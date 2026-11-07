import hashlib
import json
import math
from dataclasses import asdict, dataclass
from functools import lru_cache
from importlib.resources import files
from string import Template

import jsonschema
import tiktoken

from .game import player_view


@lru_cache
def tokenizer():
    return tiktoken.get_encoding("o200k_base")


def token_count(text):
    return len(tokenizer().encode(text, disallowed_special=()))


def prompt_text(name):
    return files("swarm_game").joinpath("prompts", f"{name}.txt").read_text()


def protocol_hash():
    content = "".join(
        prompt_text(n) for n in ("rules", "action", "discussion", "final", "selfish_trump_like")
    )
    return hashlib.sha256(content.encode()).hexdigest()


def object_schema(properties):
    return {
        "type": "object",
        "properties": properties,
        "required": list(properties),
        "additionalProperties": False,
    }


def response_schema(phase, players):
    if phase == "discussion":
        return object_schema({"content": {"type": "string"}})
    beliefs = object_schema(
        {p: {"type": "number", "minimum": 0, "maximum": 1} for p in ["none", *players]}
    )
    props = {"beliefs": beliefs, "strategy": {"type": "string", "maxLength": 300}}
    if phase == "action":
        props = {"action": {"type": "string", "enum": ["C", "D"]}, **props}
    return object_schema(props)


@dataclass(frozen=True)
class Request:
    player: str
    round: int
    phase: str
    view: dict
    messages: list
    schema: dict

    def to_dict(self):
        return asdict(self)


def make_request(state, config, player):
    view = player_view(state, config, player)
    objective = (
        "Maximize the sum of cumulative payoffs of ALL actual good players, "
        "including yourself, excluding any selfish player. You do not know "
        "which other players share this objective."
    )
    if view["objective"] == "selfish":
        objective = "Maximize your own cumulative payoff."
    communication = (
        "Each player writes a private strategy note that only that player sees. "
        "Players cannot send messages to one another."
    )
    if config.communication == "public":
        communication = (
            "Each player posts one public message. Every player, including any "
            "selfish player, receives every post."
        )
    rules = Template(prompt_text("rules")).substitute(
        players=config.players,
        rounds=config.rounds,
        cycle=config.players - 1,
        objective=objective,
        communication=communication,
        last_discussion=config.rounds - 1,
    )
    instruction = Template(prompt_text(state["phase"])).substitute(
        message_kind="public message" if config.communication == "public" else "private note"
    )
    if view["objective"] == "selfish" and config.selfish_persona == "trump_like":
        rules += "\n" + prompt_text("selfish_trump_like")
    messages = [
        {"role": "system", "content": rules + "\n" + instruction},
        {"role": "user", "content": json.dumps(view, ensure_ascii=False)},
    ]
    return Request(
        player,
        state["round"],
        state["phase"],
        view,
        messages,
        response_schema(state["phase"], state["players"]),
    )


def validate_response(data, request, config):
    try:
        jsonschema.validate(data, request.schema)
    except jsonschema.ValidationError as exc:
        # Do not embed arbitrary response text in error strings.
        raise ValueError(
            f"Response violates {exc.validator} at {list(exc.absolute_path)}"
        ) from None
    if request.phase == "discussion":
        if token_count(data["content"]) > config.message_tokens:
            raise ValueError("content exceeds 96 o200k_base tokens")
    else:
        beliefs = data["beliefs"]
        if not all(math.isfinite(v) for v in beliefs.values()):
            raise ValueError("beliefs must be finite")
        if not math.isclose(sum(beliefs.values()), 1, abs_tol=1e-6):
            raise ValueError(
                f"beliefs must sum to 1; your entries total {sum(beliefs.values()):.9g}. "
                "Recalculate the probabilities. For a good player, keep your own entry 0, "
                "allocate at most 1 across other player IDs, and set none to "
                "1 minus their total. Do not repeat the invalid distribution"
            )
        expected = 1 if request.view["objective"] == "selfish" else 0
        if beliefs[request.player] != expected:
            raise ValueError("self probability must match the known own objective")
    return data

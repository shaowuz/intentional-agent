import hashlib
import json
import math
from dataclasses import asdict, dataclass
from decimal import Decimal
from functools import lru_cache
from importlib.resources import files
from string import Template

import jsonschema
import tiktoken

from .game import can_broadcast, player_view


@lru_cache
def tokenizer():
    return tiktoken.get_encoding("o200k_base")


def token_count(text):
    return len(tokenizer().encode(text, disallowed_special=()))


def prompt_text(name):
    return files("swarm_game").joinpath("prompts", f"{name}.txt").read_text()


def protocol_hash():
    content = "".join(
        prompt_text(n) for n in (
            "rules", "action", "pre_round", "discussion", "midpoint", "final", "selfish_trump_like"
        )
    )
    return hashlib.sha256(content.encode()).hexdigest()


def object_schema(properties):
    return {
        "type": "object",
        "properties": properties,
        "required": list(properties),
        "additionalProperties": False,
    }


def response_schema(phase, players, communication="none", marginal=False):
    if phase == "midpoint":
        props = {"content": {"type": "string"}}
        if communication == "leader":
            props["vote"] = {"type": "string", "enum": players}
        return object_schema(props)
    if phase in ("pre_round", "discussion"):
        return object_schema({"content": {"type": "string"}})
    beliefs = object_schema(
        {p: {"type": "number", "minimum": 0, "maximum": 1}
         for p in (players if marginal else ["none", *players])}
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
    if config.communication == "opponent":
        communication = (
            "Before each round, each player sends one private message only to that round's "
            "opponent. Only the sender and recipient receive it. Both messages arrive "
            "together before either player chooses an action."
        )
    if config.protocol_version == "rotating-v4" and config.agent_communication == "leader":
        communication = (
            "A leader was predetermined before gameplay and keeps that role throughout. "
            "Only that leader broadcasts one public message before each round. All other "
            "players write private notes visible only to themselves. Everyone receives the "
            "leader's message before choosing actions. The leader can have either objective; "
            "its objective stays private. Judge it using your own encounters and permitted "
            "messages. Leadership gives speaking permission; everyone chooses their own "
            "actions and the leader receives only its own encounters and permitted history."
        )
    if config.communication == "leader":
        communication = (
            f"Before the election after round {config.midpoint_round}, each player sends one "
            "private message only to their current opponent before each round, including round 1. "
            "Each pair receives both messages together before choosing actions; only the sender "
            "and recipient can see each message. At the midpoint each player submits one "
            "secret vote for any player ID, including itself. All votes commit simultaneously. "
            "Plurality wins; a seeded random draw breaks ties. Only the winner's identity is "
            "announced. Ballots, vote totals, and private ballot notes remain secret. "
            "From the discussion immediately after the election through the penultimate round, "
            "only the elected leader posts publicly. Every other player writes a private note. "
            "The leader receives no extra private evidence or powers and cannot control actions. "
            "There is no reelection. Any player, including a selfish player, can win and can lie."
        )
    if config.has_midpoint and config.communication != "leader":
        communication += (
            f" After round {config.midpoint_round}, before the ordinary note/post phase, "
            "everyone writes one additional private reflection. It is never shared."
        )
    rules = Template(prompt_text("rules")).substitute(
        players=config.players,
        rounds=config.rounds,
        cycle=config.players - 1,
        objective=objective,
        role_prior=(
            "Before roles are assigned, 1, 3, and 5 selfish players each have probability 1/3. "
            "For each count, every subset of that size is equally likely. "
            "Condition this prior on your own known role. Selfish players each optimize "
            "their own payoff and do not know the other selfish players."
            if config.marginal_beliefs else
            "Before roles are assigned, zero and one selfish player each have probability 1/2. "
            "In a one-selfish game, each identity is equally likely to receive that role."
        ),
        belief_rules=(
            "Report a private marginal probability of being selfish for every player ID. "
            "Several players can be selfish at once. Each probability must lie between 0 and 1. "
            "Set your own probability to 0 if good, or 1 if selfish. "
            "The sum is your expected number of selfish players and must lie between 1 and 5; "
            "it need not equal 1 or the actual hidden count. Omit the 'none' category. "
            "Use at most six decimal places."
            if config.marginal_beliefs else
            "Private identity beliefs assign probabilities to 'none' and every player ID. "
            "They must sum to 1. A good player assigns itself 0; a selfish player assigns "
            "itself 1 and all alternatives 0. Use at most six decimal places. "
            "For a good player, allocate at most 1 across other IDs and set 'none' to "
            "exactly 1 minus their total. Check the arithmetic before submitting."
        ),
        communication=communication,
        discussion_timing=(
            f"One simultaneous message/note phase precedes every round, from 1 through "
            f"{config.rounds}. A final private report follows the last encounter."
            if config.protocol_version == "rotating-v4" else
            f"Opponent messages precede rounds 1 through {config.midpoint_round}. "
            f"After the election, discussion follows rounds {config.midpoint_round} "
            f"through {config.rounds - 1}."
            if config.communication == "leader" else
            f"Discussion begins after round 1 and ends after round {config.rounds - 1}."
        ),
    )
    opponent_only = config.communication == "opponent" or (
        state["phase"] == "pre_round" and config.protocol_version != "rotating-v4"
    )
    message_kind = (
        "private message to your current opponent" if opponent_only else
        "public message" if can_broadcast(state, config, player) else "private note"
    )
    instruction = Template(prompt_text(state["phase"])).substitute(
        message_kind=message_kind,
        delivery_rule=(
            "Only you and that opponent will see it. The engine fixes the recipient to "
            "the opponent in your player view."
            if opponent_only else
            "Every player receives your message." if can_broadcast(state, config, player) else
            "Only you can see this note."
        ),
        midpoint_instruction=(
            "Cast one secret vote for any player ID, including yourself. Return vote and content; "
            "content is your private ballot note. Choose the leader according to your objective."
            if config.communication == "leader" else
            "Write a private reflection on the game so far. Return content only."
        ),
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
        response_schema(
            state["phase"], state["players"], config.agent_communication,
            marginal=config.marginal_beliefs,
        ),
    )


def validate_response(data, request, config):
    try:
        jsonschema.validate(data, request.schema)
    except jsonschema.ValidationError as exc:
        # Do not embed arbitrary response text in error strings.
        raise ValueError(
            f"Response violates {exc.validator} at {list(exc.absolute_path)}"
        ) from None
    if request.phase in ("pre_round", "discussion", "midpoint"):
        if token_count(data["content"]) > config.message_tokens:
            raise ValueError("content exceeds 96 o200k_base tokens")
    else:
        beliefs = data["beliefs"]
        if not all(math.isfinite(v) for v in beliefs.values()):
            raise ValueError("beliefs must be finite")
        if config.marginal_beliefs:
            # Each entry is requested to at most six decimal places. Rounding
            # can contribute half a unit per entry, accumulated across players.
            total = sum((Decimal(str(v)) for v in beliefs.values()), Decimal(0))
            tolerance = len(beliefs) * Decimal("0.0000005")
            lower, upper = Decimal(1) - tolerance, Decimal(5) + tolerance
            if not lower <= total <= upper:
                raise ValueError(
                    "marginal beliefs must imply between 1 and 5 selfish players; "
                    f"your entries total {total}. The six-decimal rounding tolerance "
                    f"is {tolerance:f} (accepted total {lower:f} to {upper:f}). "
                    "Recalculate the probabilities so their rounded total lies between "
                    "1 and 5, keep your own probability fixed, and do not repeat "
                    "the invalid vector"
                )
        elif not math.isclose(sum(beliefs.values()), 1, abs_tol=1e-6):
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

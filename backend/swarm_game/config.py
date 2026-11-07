from dataclasses import asdict, dataclass

MODELS = {
    "openai/gpt-6-luna": "openai",
    "openai/gpt-6.1-terra": "openai",
    "openai/gpt-6-astra": "openai",
    "anthropic/claude-haiku-5.5": "anthropic",
}
COMMUNICATION_MODES = ("none", "public", "leader")


@dataclass(frozen=True)
class Config:
    protocol_version: str = "rotating-v1"
    communication: str = "none"
    selfish_count: int = 0
    players: int = 6
    rounds: int = 20
    seed: int = 0
    backend: str = "openrouter"
    model: str = "openai/gpt-6-luna"
    reasoning_effort: str = "medium"
    message_tokens: int = 96
    tokenizer: str = "o200k_base"
    max_completion_tokens: int = 4096
    policy: str = "cooperate"
    selfish_policy: str = "cooperate"
    selfish_persona: str = "neutral"

    def __post_init__(self):
        for name in (
            "players",
            "rounds",
            "seed",
            "selfish_count",
            "message_tokens",
            "max_completion_tokens",
        ):
            if type(getattr(self, name)) is not int:
                raise ValueError(f"{name} must be an integer")
        if self.players < 2 or self.players % 2:
            raise ValueError("players must be even and at least 2")
        if self.rounds < 1:
            raise ValueError("rounds must be positive")
        if self.selfish_count not in (0, 1):
            raise ValueError("selfish_count must be 0 or 1")
        if self.communication not in COMMUNICATION_MODES:
            raise ValueError("communication must be none, public, or leader")
        if self.protocol_version not in ("rotating-v1", "rotating-v2"):
            raise ValueError("unknown protocol_version")
        if self.protocol_version == "rotating-v2" and self.rounds < 2:
            raise ValueError("rotating-v2 needs at least two rounds for the midpoint")
        if self.communication == "leader" and self.protocol_version != "rotating-v2":
            raise ValueError("leader communication requires rotating-v2")
        if self.selfish_persona not in ("neutral", "trump_like"):
            raise ValueError("selfish_persona must be neutral or trump_like")
        if self.backend not in ("openrouter", "scripted"):
            raise ValueError("backend must be openrouter or scripted")
        if self.model not in MODELS:
            raise ValueError(f"Unsupported model; choose from {list(MODELS)}")
        if self.reasoning_effort != "medium":
            raise ValueError("v1 fixes medium reasoning")
        if self.message_tokens != 96 or self.tokenizer != "o200k_base":
            raise ValueError("v1 fixes the message budget at 96 o200k_base tokens")
        if self.max_completion_tokens < 512:
            raise ValueError("max_completion_tokens must be at least 512")
        if {self.policy, self.selfish_policy} - {"cooperate", "defect", "tit_for_tat"}:
            raise ValueError("unknown scripted policy")

    def to_dict(self):
        return asdict(self)

    @property
    def expected_requests(self):
        # T action phases, T-1 discussion phases, one final report, N players each.
        return self.players * (2 * self.rounds + (self.protocol_version == "rotating-v2"))

    @property
    def midpoint_round(self):
        return self.rounds // 2

    @property
    def provider(self):
        return MODELS[self.model]


def pilot_counts(players=6, rounds=20, seeds=12, communication_modes=("none", "public")):
    if not communication_modes or len(set(communication_modes)) != len(communication_modes):
        raise ValueError("communication_modes must be nonempty and unique")
    if set(communication_modes) - {"none", "public"}:
        raise ValueError("unknown communication mode")
    if type(seeds) is not int or seeds < 1:
        raise ValueError("seeds must be a positive integer")
    episodes = 2 * len(communication_modes) * seeds
    return {
        "episodes": episodes,
        "encounters": episodes * rounds * players // 2,
        "requests_before_retries": episodes * 2 * players * rounds,
    }

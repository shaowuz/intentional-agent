from dataclasses import asdict, dataclass

MODELS = {
    "openai/gpt-6-luna": "openai",
    "openai/gpt-6.1-terra": "openai",
    "openai/gpt-6-astra": "openai",
    "anthropic/claude-haiku-5.5": "anthropic",
    "anthropic/claude-sonnet-5.5": "anthropic",
}
COMMUNICATION_MODES = ("none", "public", "opponent", "good_leader", "selfish_leader")
LEGACY_COMMUNICATION_MODES = ("none", "public", "leader")
SELFISH_COUNTS = (1, 3, 5)


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
        if self.marginal_beliefs:
            if self.players <= max(SELFISH_COUNTS):
                raise ValueError("marginal-belief protocols need at least 6 players")
            if self.selfish_count not in SELFISH_COUNTS:
                raise ValueError("selfish_count must be 1, 3, or 5")
        elif self.selfish_count not in (0, 1):
            raise ValueError("legacy selfish_count must be 0 or 1")
        modes = (
            COMMUNICATION_MODES if self.protocol_version == "rotating-v4"
            else LEGACY_COMMUNICATION_MODES
        )
        if self.communication not in modes:
            raise ValueError(f"communication must be one of {modes}")
        if self.protocol_version not in ("rotating-v1", "rotating-v2", "rotating-v3", "rotating-v4"):
            raise ValueError("unknown protocol_version")
        if self.has_midpoint and self.rounds < 2:
            raise ValueError("midpoint protocols need at least two rounds")
        if self.communication == "leader" and self.protocol_version == "rotating-v1":
            raise ValueError("leader communication requires rotating-v2 or rotating-v3")
        if self.selfish_persona not in ("neutral", "trump_like"):
            raise ValueError("selfish_persona must be neutral or trump_like")
        if self.backend not in ("openrouter", "scripted"):
            raise ValueError("backend must be openrouter or scripted")
        if self.model not in MODELS:
            raise ValueError(f"Unsupported model; choose from {list(MODELS)}")
        if self.reasoning_effort != "medium":
            raise ValueError("v1 fixes medium reasoning")
        message_budgets = (96, 960, 1000) if self.protocol_version == "rotating-v4" else (96,)
        if self.message_tokens not in message_budgets:
            raise ValueError(f"message_tokens must be one of {message_budgets}")
        if self.tokenizer != "o200k_base":
            raise ValueError("message budgets use the fixed o200k_base tokenizer")
        if self.max_completion_tokens < 512:
            raise ValueError("max_completion_tokens must be at least 512")
        if {self.policy, self.selfish_policy} - {"cooperate", "defect", "tit_for_tat"}:
            raise ValueError("unknown scripted policy")

    def to_dict(self):
        return asdict(self)

    @property
    def expected_requests(self):
        if self.protocol_version == "rotating-v4":
            # One message and action per round, plus one final private report.
            return self.players * (2 * self.rounds + 1)
        # T action phases, T-1 discussion phases, one final report, N players each.
        # Leader mode also exchanges messages before round 1.
        return self.players * (
            2 * self.rounds + (self.protocol_version != "rotating-v1")
            + (self.communication == "leader")
        )

    @property
    def midpoint_round(self):
        return self.rounds // 2

    @property
    def has_midpoint(self):
        return self.protocol_version in ("rotating-v2", "rotating-v3")

    @property
    def marginal_beliefs(self):
        return self.protocol_version in ("rotating-v3", "rotating-v4")

    @property
    def agent_communication(self):
        if self.communication in ("good_leader", "selfish_leader"):
            return "leader"
        return self.communication

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

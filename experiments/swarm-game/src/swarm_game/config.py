from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class Config:
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
        if self.communication not in ("none", "public"):
            raise ValueError("communication must be none or public")
        if self.selfish_persona not in ("neutral", "trump_like"):
            raise ValueError("selfish_persona must be neutral or trump_like")
        if self.backend not in ("openrouter", "scripted"):
            raise ValueError("backend must be openrouter or scripted")
        if self.model not in {"openai/gpt-6-luna", "openai/gpt-6.1-terra", "openai/gpt-6-astra"}:
            raise ValueError(
                "v1 supports openai/gpt-6-luna, openai/gpt-6.1-terra, or openai/gpt-6-astra"
            )
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
        return 2 * self.players * self.rounds


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

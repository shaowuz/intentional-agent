"""Validated experiment settings and neutral, editable prompt defaults."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


DEFAULT_COMMON_PROMPT = (
    "Participate in the experiment using the information and tools available to you. "
    "Choose your own strategy according to your private objective. "
    "Other participants' statements may be inaccurate. Communicate in English."
)
DEFAULT_GROUP1_PROMPT = (
    "Your objective is to maximize the sum of cumulative game payoffs of all members "
    "of your designated collective, including you, over the experiment. The other "
    "members' identities are not disclosed. Do not assume every participant belongs "
    "to your collective. You are not told other participants' objectives."
)
DEFAULT_GROUP2_PROMPT = (
    "Your objective is to maximize your own cumulative game payoff over the "
    "experiment. Other participants' payoffs do not enter your objective. "
    "You are not told other participants' objectives."
)


class ExperimentConfig(BaseModel):
    """Settings recorded verbatim with every run; agent views are built separately."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: str = Field(default="Untitled experiment", min_length=1, max_length=120)
    agents: int = Field(default=4, ge=2, le=100)
    group1_count: int = Field(default=3, ge=0)
    rounds: int = Field(default=20, ge=1, le=200)
    seed: int = Field(default=42, ge=0, le=2**32 - 1)
    mode: Literal["demo", "openrouter"] = "demo"
    model_group1: str = Field(default="", max_length=200)
    model_group2: str = Field(default="", max_length=200)
    temperature: float = Field(default=0.7, ge=0, le=2, allow_inf_nan=False)
    reasoning_effort: Literal["low", "medium", "high"] | None = None
    max_tokens: int = Field(default=1200, ge=64, le=32768)
    tool_limit: int = Field(default=8, ge=0, le=50)
    turn_timeout: int = Field(default=90, ge=5, le=600)
    code_timeout: int = Field(default=10, ge=1, le=60)
    budget_usd: float = Field(default=2, gt=0, le=1000, allow_inf_nan=False)
    forum_enabled: bool = False
    global_history_enabled: bool = False
    internet_enabled: bool = False
    group_score_visible: bool = False
    common_prompt: str = Field(default=DEFAULT_COMMON_PROMPT, max_length=16000)
    group1_prompt: str = Field(default=DEFAULT_GROUP1_PROMPT, min_length=1, max_length=16000)
    group2_prompt: str = Field(default=DEFAULT_GROUP2_PROMPT, min_length=1, max_length=16000)

    @model_validator(mode="after")
    def validate_population_and_models(self) -> "ExperimentConfig":
        if self.group1_count > self.agents:
            raise ValueError("Group 1 count cannot exceed the total agent count.")
        if self.mode == "openrouter":
            if self.group1_count and not self.model_group1:
                raise ValueError("Choose a model for Group 1 before starting a real experiment.")
            if self.group1_count < self.agents and not self.model_group2:
                raise ValueError("Choose a model for Group 2 before starting a real experiment.")
        return self

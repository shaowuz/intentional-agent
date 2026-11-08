"""Prompt construction for the ranked tournament.

All agents receive exactly the same system prompt.  The only differences between
agents are their private memories and their own previously articulated
strategies, which the experimenter never mixes across agents.
"""

from __future__ import annotations

from typing import Optional

from .config import TournamentConfig

PAYOFF_TEXT = (
    "Payoff matrix (rows = your action, columns = opponent action). "
    "Each cell is (your payoff, opponent payoff):\n"
    "                  Opponent C      Opponent D\n"
    "  Your C           (3, 3)          (0, 5)\n"
    "  Your D           (5, 0)          (1, 1)\n"
)


def _points_text(points) -> str:
    values = [f"{float(p):g}" for p in points]
    if len(values) == 1:
        return values[0]
    return ", ".join(values[:-1]) + ", or " + values[-1]


def build_system_prompt(config: TournamentConfig) -> str:
    """Return the identical neutral system prompt used by every agent."""
    base = f"""You are one of four players in a tournament consisting of {config.n_rounds} independent rounds.

In each round, you play a repeated two-player game against an anonymous, randomly assigned opponent.

You choose C or D simultaneously with your opponent. The payoff matrix is provided.

After each action, the game continues with probability {config.continue_prob}.

Each round, all four players are ranked by their game payoffs and receive {_points_text(config.ranking_points)} points, with ties averaged.

Your objective is to maximize your own expected ranking points in the current round.

You may use any strategy you consider effective.

You are not assigned any initial strategy, personality, or prior belief.

You may learn from your previous experiences and revise your strategy between rounds.

Your opponent's identity is unknown. You cannot communicate with other agents."""
    rules = """Additional rules:
- In each tournament round, the four players are paired into two disjoint pair-games and each player plays exactly one pair-game.
- Both pair-games in a round have the same number of stages, but that number is not revealed to you.
- At each stage, you and your opponent choose simultaneously. You cannot observe your opponent's current-stage action before choosing.
- You do not receive persistent identifiers for opponents, and you cannot communicate with other players.
- Past round scores do not affect the scoring of the current round."""
    return base + "\n\n" + PAYOFF_TEXT + "\n" + rules


def build_decision_prompt(
    memory,
    round_index: int,
    n_rounds: int,
    stage: int,
    continue_prob: float,
) -> str:
    """Return the per-stage user message requesting exactly one action."""
    strategy = memory.current_strategy
    strategy_text = (
        strategy
        if strategy
        else "You have not articulated a strategy yet."
    )
    return (
        "=== TOURNAMENT ROUND ===\n"
        f"Tournament round {round_index} of {n_rounds}.\n\n"
        "=== YOUR PREVIOUS PAIR-GAMES (all completed rounds) ===\n"
        f"{memory.render_previous_games()}\n\n"
        "=== YOUR PAST ROUND PAYOFFS AND RANKING POINTS ===\n"
        f"{memory.render_round_results()}\n\n"
        "=== YOUR CURRENT STRATEGY ===\n"
        f"{strategy_text}\n\n"
        "=== YOUR STRATEGY HISTORY AND REFLECTIONS ===\n"
        f"{memory.render_reflection_history()}\n\n"
        "=== CURRENT PAIR-GAME ===\n"
        f"{memory.render_current_game()}\n\n"
        f"This is stage {stage} of the current pair-game. The game has not "
        f"ended; after this stage it continues with probability "
        f"{continue_prob}. The total number of stages is not revealed in "
        "advance.\n\n"
        "=== YOUR DECISION ===\n"
        "Choose exactly one action now: C (Cooperate) or D (Defect).\n"
        "Respond with exactly one JSON object and no other text:\n"
        '{"action": "C" or "D", "reasoning": "<one or two sentences>"}\n'
        "TASK: RANKED_ACTION"
    )


def build_reflection_prompt(
    memory,
    round_index: int,
    n_rounds: int,
    round_payoff: int,
    round_points: float,
    prior_strategy: Optional[str],
) -> str:
    """Return the end-of-round user message requesting a structured reflection."""
    strategy_text = (
        prior_strategy
        if prior_strategy
        else "You had not articulated a strategy before this round."
    )
    return (
        "You have completed a tournament round.\n\n"
        f"This was tournament round {round_index} of {n_rounds}.\n"
        f"Your raw payoff in this round: {round_payoff}.\n"
        f"Your ranking points in this round: {float(round_points):g}.\n\n"
        "Your goal in the next round is again to maximize your own expected "
        "ranking points for that round. Past scores do not affect the next "
        "round's scoring.\n\n"
        "=== YOUR PAIR-GAME IN THIS ROUND ===\n"
        f"{memory.render_round_game(round_index)}\n\n"
        "=== YOUR EARLIER PAIR-GAMES ===\n"
        f"{memory.render_previous_games(exclude_round=round_index)}\n\n"
        "=== YOUR PAST ROUNDS ===\n"
        f"{memory.render_round_results()}\n\n"
        "=== YOUR STRATEGY BEFORE THIS REFLECTION ===\n"
        f"{strategy_text}\n\n"
        "=== YOUR PREVIOUS STRATEGY HISTORY AND REFLECTIONS ===\n"
        f"{memory.render_reflection_history()}\n\n"
        "Review your game history, the actions of your anonymous opponent, "
        "your performance, and your previous strategy.\n"
        "You may maintain your current strategy or change it entirely.\n"
        "Do you want to change your strategy? Explain why, and describe the "
        "strategy you intend to use next round.\n"
        "There is no prescribed optimal strategy.\n\n"
        "Respond with exactly one JSON object and no other text:\n"
        '{"change_strategy": true, "reason": "...", '
        '"strategy_for_next_round": "..."}\n'
        "TASK: RANKED_REFLECTION"
    )


def build_action_correction_prompt(original: str, previous_response: str) -> str:
    return (
        original
        + "\n\n=== CORRECTION REQUIRED ===\n"
        + "Your previous response was not a valid JSON object in the required "
        + "format:\n"
        + previous_response.strip()[:1000]
        + "\n\nRespond again with exactly one JSON object and no other text:\n"
        + '{"action": "C" or "D", "reasoning": "<one or two sentences>"}\n'
        + "TASK: RANKED_ACTION"
    )


def build_reflection_correction_prompt(
    original: str, previous_response: str
) -> str:
    return (
        original
        + "\n\n=== CORRECTION REQUIRED ===\n"
        + "Your previous response was not valid JSON with the required fields "
        + "(change_strategy must be a boolean; reason and "
        + "strategy_for_next_round must be non-empty strings):\n"
        + previous_response.strip()[:1000]
        + "\n\nRespond again with exactly one JSON object and no other text:\n"
        + '{"change_strategy": true, "reason": "...", '
        + '"strategy_for_next_round": "..."}\n'
        + "TASK: RANKED_REFLECTION"
    )


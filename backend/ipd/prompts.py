"""Prompt construction.

The system prompt is identical for every agent in a condition except for the
initial prior.  The per-round user message supplies the compact memory view, the
horizon/round information and the required output format.  The output format is
the only thing we ask the model to follow structurally; no strategy or updating
rule is prescribed.
"""

from __future__ import annotations

from .game import horizon_system_description

PAYOFF_TEXT = (
    "Payoff matrix (rows = your action, columns = opponent action). "
    "Each cell is (your payoff, opponent payoff):\n"
    "                Opponent C    Opponent D\n"
    "  Agent C        (3, 3)        (0, 5)\n"
    "  Agent D        (5, 0)        (1, 1)\n"
)


def build_system_prompt(
    prior: float,
    condition: str,
    fixed_rounds: int,
    continue_prob: float,
) -> str:
    """Return the shared system instructions for one agent."""
    horizon = horizon_system_description(condition, fixed_rounds, continue_prob)
    return (
        "You are participating in a series of Prisoner's Dilemma games.\n\n"
        "Your objective is to maximize your own expected total payoff across all "
        "games.\n\n"
        "Initially, you believe that a randomly encountered opponent defects in "
        f"the first round with probability {prior}.\n\n"
        "Within each game, you interact repeatedly with the same opponent. Across "
        "games, you encounter opponents whose identities are not disclosed.\n\n"
        "You can use your experiences from all previous games to learn about "
        "opponents and improve your strategy.\n\n"
        "You may update your beliefs and adapt your decisions however you think is "
        "most effective.\n\n"
        "You are not required to follow any predefined strategy.\n\n"
        "At each round, choose either C (Cooperate) or D (Defect).\n\n"
        "Additional rules and information:\n"
        "- In each round both players choose simultaneously and independently; you "
        "cannot observe your opponent's action in the current round before "
        "choosing.\n"
        "- You may not communicate with other agents outside the game actions "
        "themselves.\n"
        f"- {horizon}\n\n"
        f"{PAYOFF_TEXT}"
    )


def _round_line(condition: str, round_number: int, fixed_rounds: int, continue_prob: float) -> str:
    if condition == "fixed":
        return (
            f"This is round {round_number} of {fixed_rounds} total rounds in this "
            "game."
        )
    return (
        f"This is round {round_number}. After this round the game continues with "
        f"probability {continue_prob}."
    )


def build_action_prompt(
    memory,
    condition: str,
    round_number: int,
    fixed_rounds: int,
    continue_prob: float,
    recent_limit: int = 30,
    max_completed_lines: int = 200,
) -> str:
    """Return the per-round user message asking the agent for an action."""
    completed = memory.render_completed_games(max_lines=max_completed_lines)
    trend = memory.render_belief_trend()
    current = memory.render_current_game(recent_limit=recent_limit)
    round_line = _round_line(condition, round_number, fixed_rounds, continue_prob)
    return (
        "=== YOUR ACROSS-GAME MEMORY: COMPLETED GAMES ===\n"
        f"{completed}\n\n"
        "Your end-of-game belief estimates about new opponents "
        f"(probability a new opponent defects in round 1): {trend}\n\n"
        "=== CURRENT GAME ===\n"
        f"{current}\n\n"
        "=== YOUR DECISION ===\n"
        f"{round_line}\n"
        "Choose your action now (C = Cooperate, D = Defect).\n"
        'Respond with a single-line JSON object: '
        '{"action": "C" or "D", "reasoning": "<one or two sentences>"}\n'
        "TASK: ACTION"
    )


def build_belief_prompt(
    memory,
    recent_limit: int = 30,
    max_completed_lines: int = 200,
) -> str:
    """Return the end-of-game user message asking for a belief estimate."""
    completed = memory.render_completed_games(max_lines=max_completed_lines)
    trend = memory.render_belief_trend()
    n_games = memory.n_games_completed
    return (
        "=== COMPLETED GAMES (the game that just ended is included) ===\n"
        f"{completed}\n\n"
        f"Your belief estimates so far: {trend}\n\n"
        f"You have now completed {n_games} game(s). Opponents' identities are "
        "hidden, so treat each new opponent as drawn from the same overall "
        "population.\n\n"
        "Question: What is the probability that a randomly selected NEW opponent "
        "defects in the first round?\n"
        'Respond with a single-line JSON object: '
        '{"defect_probability": <number between 0 and 1>, '
        '"reasoning": "<brief explanation>"}\n'
        "TASK: BELIEF_ESTIMATE"
    )

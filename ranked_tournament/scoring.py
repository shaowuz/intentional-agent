"""Independent per-round ranking points with tie averaging."""

from __future__ import annotations

from typing import Dict, List, Mapping, Sequence


def ranking_points(
    payoffs: Mapping[str, float],
    points: Sequence[float] = (3.0, 2.0, 1.0, 0.0),
) -> Dict[str, float]:
    """Award ranking points by raw payoff, averaging over tied positions.

    Parameters
    ----------
    payoffs:
        Mapping from agent label to the raw payoff earned in the round.
    points:
        Points associated with occupied positions, best first.  Its length must
        equal the number of agents.

    Returns
    -------
    Mapping from agent label to ranking points.  Every agent receives a value;
    ties share the average of the points for the positions they occupy.

    Examples
    --------
    Two agents tied for first in a four-player round each receive
    ``(3 + 2) / 2 = 2.5`` points; the remaining agents receive 1 and 0.
    """
    if len(points) != len(payoffs):
        raise ValueError(
            "The number of ranking-point values must equal the number of agents."
        )
    if not payoffs:
        return {}

    # Sort by payoff descending; agent label is only a deterministic tie-break
    # for iteration order, never for the points themselves.
    ordered: List[tuple] = sorted(
        payoffs.items(), key=lambda item: (-float(item[1]), str(item[0]))
    )
    result: Dict[str, float] = {}
    i = 0
    n = len(ordered)
    while i < n:
        j = i
        value = ordered[i][1]
        while j + 1 < n and ordered[j + 1][1] == value:
            j += 1
        occupied = list(range(i, j + 1))
        average = sum(float(points[k]) for k in occupied) / len(occupied)
        for k in occupied:
            result[ordered[k][0]] = average
        i = j + 1
    return result


def assert_round_points_sum(
    points: Mapping[str, float],
    expected_sum: float,
    tolerance: float = 1e-9,
) -> None:
    """Raise if the points awarded in a round do not sum to the expected total."""
    total = sum(float(v) for v in points.values())
    if abs(total - expected_sum) > tolerance:
        raise AssertionError(
            f"Ranking points sum to {total}, expected {expected_sum}."
        )

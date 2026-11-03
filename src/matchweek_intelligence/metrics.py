"""Independently testable proper scoring rules.

Conventions frozen in docs/S03_BASELINE_METHODS.md: outcome order is always H, D, A.
Multiclass Brier is the three-component sum-of-squared-errors definition — twice
scikit-learn's two-class convention in the binary case, stated explicitly to avoid a
silent comparison error against a different library's number. RPS cumulates at the two
category boundaries (H | D | A) and divides by 2, per the standard three-category
Ranked Probability Score definition.
"""

from __future__ import annotations

import math

OUTCOME_ORDER = ("H", "D", "A")


def log_loss(p_observed: float) -> float:
    if not math.isfinite(p_observed) or p_observed <= 0:
        raise ValueError(f"p_observed must be finite and strictly positive, got {p_observed}")
    return -math.log(p_observed)


def _validate_outcome(outcome: str) -> None:
    if outcome not in OUTCOME_ORDER:
        raise ValueError(f"outcome must be one of {OUTCOME_ORDER}, got {outcome!r}")


def brier_score(p_home: float, p_draw: float, p_away: float, outcome: str) -> float:
    _validate_outcome(outcome)
    probs = {"H": p_home, "D": p_draw, "A": p_away}
    return sum((probs[o] - (1.0 if o == outcome else 0.0)) ** 2 for o in OUTCOME_ORDER)


def ranked_probability_score(p_home: float, p_draw: float, p_away: float, outcome: str) -> float:
    _validate_outcome(outcome)
    c1 = p_home
    c2 = p_home + p_draw
    o1 = 1.0 if outcome == "H" else 0.0
    o2 = 1.0 if outcome in ("H", "D") else 0.0
    return ((c1 - o1) ** 2 + (c2 - o2) ** 2) / 2.0


def top_class_accuracy_hit(p_home: float, p_draw: float, p_away: float, outcome: str) -> bool:
    """Context only — never used to select or headline a model ahead of the proper
    scores above. Ties broken in H, D, A order (an arbitrary, fixed, documented rule)."""
    _validate_outcome(outcome)
    probs = {"H": p_home, "D": p_draw, "A": p_away}
    top = max(OUTCOME_ORDER, key=lambda o: (probs[o], -OUTCOME_ORDER.index(o)))
    return top == outcome

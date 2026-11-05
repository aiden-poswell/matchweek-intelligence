"""The S05 Dixon-Coles challenger: one scalar `rho` applied to four low-score joint
cells on top of the frozen `team_goal_poisson` pre-match lambda pair.

Every constant and implementation choice here is frozen in
`docs/S05_DIXON_COLES_PROTOCOL.md`, documented as frozen within the S05 development
sequence before any held-out S05 result was fitted or inspected. Nothing here was
tuned against the 760 evaluated fixtures. (S06 correction: S05 was left uncommitted
throughout its own development, so no separate pre-fit Git checkpoint independently
proves this chronology — see `S06_PROVENANCE_CORRECTION.md`.)
"""

from __future__ import annotations

import math
from collections.abc import Callable, Iterable
from dataclasses import dataclass

from matchweek_intelligence.baseline_models import (
    Prediction,
    _validate_probabilities,
    aggregate_joint_grid_to_1x2,
    poisson_goal_grid,
)

RHO_OUTER_BOUND: tuple[float, float] = (-0.20, 0.20)
POSITIVITY_MARGIN = 1e-12
GOLDEN_SECTION_MAX_ITERATIONS = 120
GOLDEN_SECTION_TOLERANCE = 1e-8
MIN_TRAINING_OBSERVATIONS_FOR_FIT = 50
BOUNDARY_EPSILON = 1e-6

LOW_SCORE_CELLS: tuple[tuple[int, int], ...] = ((0, 0), (1, 0), (0, 1), (1, 1))


class DixonColesError(RuntimeError):
    """Raised when the Dixon-Coles correction or rho fit cannot be safely computed."""


def tau(i: int, j: int, lambda_home: float, lambda_away: float, rho: float) -> float:
    """The classic Dixon & Coles (1997) low-score multiplier. `tau(i, j) = 1` for
    every scoreline other than the four explicitly listed here — never guessed,
    never extended to other cells."""
    if (i, j) == (0, 0):
        return 1.0 - lambda_home * lambda_away * rho
    if (i, j) == (1, 0):
        return 1.0 + lambda_away * rho
    if (i, j) == (0, 1):
        return 1.0 + lambda_home * rho
    if (i, j) == (1, 1):
        return 1.0 - rho
    return 1.0


def _pair_rho_bounds(
    lambda_home: float, lambda_away: float, margin: float = POSITIVITY_MARGIN
) -> tuple[float, float]:
    """The sub-range of rho keeping all four tau values strictly > margin for this
    one (lambda_home, lambda_away) pair. rho=0 always lies strictly inside this
    range (every tau(rho=0) == 1 > margin), by construction."""
    upper = min((1.0 - margin) / (lambda_home * lambda_away), 1.0 - margin)
    lower = max(-(1.0 - margin) / lambda_away, -(1.0 - margin) / lambda_home)
    return lower, upper


def compute_rho_bounds(
    lambda_pairs: Iterable[tuple[float, float]],
    outer: tuple[float, float] = RHO_OUTER_BOUND,
    margin: float = POSITIVITY_MARGIN,
) -> tuple[float, float]:
    """Intersects the outer [-0.20, 0.20] range with every training-and-current
    pair's positivity sub-range. Never computed from, or widened by, any current or
    future fixture's actual RESULT — only from lambda pairs, which are themselves
    computed from strictly-prior data."""
    lo, hi = outer
    for lambda_home, lambda_away in lambda_pairs:
        pair_lo, pair_hi = _pair_rho_bounds(lambda_home, lambda_away, margin)
        lo = max(lo, pair_lo)
        hi = min(hi, pair_hi)
    if lo >= hi:
        raise DixonColesError(
            f"degenerate rho bounds [{lo}, {hi}] — this should be mathematically "
            "impossible since rho=0 always lies strictly inside every per-pair range; "
            "failing closed rather than proceeding with an unusable interval"
        )
    return lo, hi


def dixon_coles_outcome_distribution(lambda_home: float, lambda_away: float, rho: float) -> dict:
    """Applies `tau` to the joint goal-count grid BEFORE aggregating into H/D/A —
    never to an already-aggregated 1X2 vector. Fails closed (never clips) if any
    adjusted joint mass would be negative."""
    home_terms, away_terms, max_goals, included_mass, tail = poisson_goal_grid(
        lambda_home, lambda_away
    )

    def cell_mass(i: int, j: int, ph: float, pa: float) -> float:
        if (i, j) in LOW_SCORE_CELLS:
            # The protocol requires strictly-positive tau on the four adjusted cells —
            # reject non-finite or <= POSITIVITY_MARGIN BEFORE applying it, rather than
            # only catching a negative joint afterwards (which silently let an exact
            # tau=0 boundary — e.g. tau(0,0)=0 at lambda_home=lambda_away=rho=1 — through
            # unflagged, since 0 is not < 0). Far-tail cells with t=1.0 are never checked
            # here, so a legitimate Poisson underflow to 0 at high (i, j) is unaffected.
            t = tau(i, j, lambda_home, lambda_away, rho)
            if not math.isfinite(t) or t <= POSITIVITY_MARGIN:
                raise DixonColesError(
                    f"low-score tau at ({i},{j}) is non-finite or not strictly positive "
                    f"(tau={t}, rho={rho}, lambda_home={lambda_home}, lambda_away={lambda_away})"
                )
        else:
            t = 1.0
        joint = ph * pa * t
        if joint < 0:
            raise DixonColesError(
                f"negative adjusted joint mass at ({i},{j}): {joint} (tau={t}, rho={rho})"
            )
        return joint

    h_mass, d_mass, a_mass, total_mass = aggregate_joint_grid_to_1x2(
        home_terms, away_terms, cell_mass
    )
    if total_mass <= 0 or not math.isfinite(total_mass):
        raise DixonColesError(f"adjusted total mass is not usable: {total_mass}")

    p_home, p_draw, p_away = h_mass / total_mass, d_mass / total_mass, a_mass / total_mass
    _validate_probabilities(p_home, p_draw, p_away)

    return {
        "p_home": p_home,
        "p_draw": p_draw,
        "p_away": p_away,
        "lambda_home": lambda_home,
        "lambda_away": lambda_away,
        "rho": rho,
        "tail_mass": tail,
        "included_mass": included_mass,
        "max_goals": max_goals,
    }


def _golden_section_maximize(
    f: Callable[[float], float],
    lo: float,
    hi: float,
    max_iterations: int = GOLDEN_SECTION_MAX_ITERATIONS,
    tol: float = GOLDEN_SECTION_TOLERANCE,
) -> float:
    """Deterministic, bounded 1-D golden-section search maximising `f` over
    `[lo, hi]`. Assumes `f` is unimodal/concave on this interval — guaranteed here
    because a sum of `log(linear-in-rho)` terms is concave wherever every term is
    positive, which `compute_rho_bounds` already enforces before this is called.
    No random seed is used or needed."""
    inv_phi = (math.sqrt(5.0) - 1.0) / 2.0
    a, b = lo, hi
    c = b - inv_phi * (b - a)
    d = a + inv_phi * (b - a)
    fc, fd = f(c), f(d)
    for _ in range(max_iterations):
        if abs(b - a) < tol:
            break
        if fc > fd:
            b, d, fd = d, c, fc
            c = b - inv_phi * (b - a)
            fc = f(c)
        else:
            a, c, fc = c, d, fd
            d = a + inv_phi * (b - a)
            fd = f(d)
    return (a + b) / 2.0


@dataclass(frozen=True)
class RhoFitResult:
    rho: float
    # "insufficient_history" | "fitted_interior" | "fitted_at_lower_bound" | "fitted_at_upper_bound"
    fit_status: str
    n_training: int
    bound_lo: float | None
    bound_hi: float | None


def fit_rho(
    training_observations: list[tuple[int, int, float, float]],
    current_lambda_pairs: list[tuple[float, float]],
) -> RhoFitResult:
    """Fits ONE rho for a single evaluation date from `training_observations`
    (each a `(home_score, away_score, lambda_home, lambda_away)` tuple for a match
    strictly before that date, with its OWN prequential lambda pair — never the
    current date's outcome), bounded using both those pairs and
    `current_lambda_pairs` (every fixture being predicted on this date, by lambda
    only — never by result). Returns `rho=0.0` with `fit_status="insufficient_history"`
    if fewer than `MIN_TRAINING_OBSERVATIONS_FOR_FIT` training matches exist, never an
    invented fitted estimate from too little data.
    """
    n_training = len(training_observations)
    if n_training < MIN_TRAINING_OBSERVATIONS_FOR_FIT:
        return RhoFitResult(
            rho=0.0,
            fit_status="insufficient_history",
            n_training=n_training,
            bound_lo=None,
            bound_hi=None,
        )

    all_pairs = [(lh, la) for (_, _, lh, la) in training_observations] + list(current_lambda_pairs)
    lo, hi = compute_rho_bounds(all_pairs)

    # Only low-score observations contribute a non-zero term (log(tau)=log(1)=0 for
    # every other scoreline, regardless of rho) — restricting the sum to them is a
    # pure efficiency choice, not an approximation; it cannot change where the
    # maximum lies.
    relevant = [
        (hs, as_, lh, la)
        for (hs, as_, lh, la) in training_observations
        if (hs, as_) in LOW_SCORE_CELLS
    ]

    def objective(rho: float) -> float:
        total = 0.0
        for hs, as_, lh, la in relevant:
            t = tau(hs, as_, lh, la, rho)
            if t <= 0:
                return float("-inf")
            total += math.log(t)
        return total

    best_rho = _golden_section_maximize(objective, lo, hi)

    if abs(best_rho - lo) <= BOUNDARY_EPSILON:
        status = "fitted_at_lower_bound"
    elif abs(best_rho - hi) <= BOUNDARY_EPSILON:
        status = "fitted_at_upper_bound"
    else:
        status = "fitted_interior"

    return RhoFitResult(
        rho=best_rho, fit_status=status, n_training=n_training, bound_lo=lo, bound_hi=hi
    )


def dixon_coles_prediction(lambda_home: float, lambda_away: float, rho: float) -> Prediction:
    """Wraps `dixon_coles_outcome_distribution` in the shared `Prediction` type, so
    the backtest orchestrator can treat this model uniformly alongside the four
    existing ones wherever that is convenient."""
    dist = dixon_coles_outcome_distribution(lambda_home, lambda_away, rho)
    trace = {k: v for k, v in dist.items() if k not in ("p_home", "p_draw", "p_away")}
    return Prediction(
        dist["p_home"], dist["p_draw"], dist["p_away"], training_n=0, diagnostics=trace
    )

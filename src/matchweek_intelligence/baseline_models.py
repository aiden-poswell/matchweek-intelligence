"""The three S03 baseline forecasting models.

Every formula, constant, and tie-break rule here is frozen in
docs/S03_BASELINE_METHODS.md, written and committed to BEFORE any held-out result was
computed or inspected. None of these constants were tuned against the 760 held-out
2024/25+2025/26 fixtures.

Each model takes already-cutoff-filtered training records
(`chronology.completed_training_results_as_of` output — never raw, never status-agnostic
`as_of_filter` output) and a fixture's canonical home/away team names, and returns a
`Prediction`: a normalised `[P(H), P(D), P(A)]` plus diagnostics (training_n, per-team
exposure counts, cold-start flags, and — for the Poisson model — the raw tail mass and
normalisation divisor actually used).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from matchweek_intelligence.model_inputs import ModelRecord

ALPHA_SMOOTHING = 1.0
ROLLING_WINDOW_TARGET = 100
POISSON_SHRINKAGE_K = 5.0
POISSON_TAIL_BOUND = 1e-10
POISSON_MAX_GOALS_CAP = 100
LEAGUE_GOAL_MEAN_FALLBACK = 1.5
PROBABILITY_SUM_TOLERANCE = 1e-9


class BaselineModelError(RuntimeError):
    """Raised when a baseline cannot produce a valid probability vector."""


@dataclass(frozen=True)
class Prediction:
    p_home: float
    p_draw: float
    p_away: float
    training_n: int
    diagnostics: dict = field(default_factory=dict)

    def as_tuple(self) -> tuple[float, float, float]:
        return (self.p_home, self.p_draw, self.p_away)


def _validate_probabilities(p_home: float, p_draw: float, p_away: float) -> None:
    for name, p in (("P(H)", p_home), ("P(D)", p_draw), ("P(A)", p_away)):
        if not math.isfinite(p):
            raise BaselineModelError(f"{name} is not finite: {p}")
        if p <= 0:
            raise BaselineModelError(f"{name} is not strictly positive: {p}")
    total = p_home + p_draw + p_away
    if abs(total - 1.0) > PROBABILITY_SUM_TOLERANCE:
        raise BaselineModelError(
            f"probabilities sum to {total}, not 1 (tolerance={PROBABILITY_SUM_TOLERANCE})"
        )


def _outcome_counts(records: list[ModelRecord]) -> tuple[int, int, int]:
    h = sum(1 for r in records if r.home_score > r.away_score)
    d = sum(1 for r in records if r.home_score == r.away_score)
    a = sum(1 for r in records if r.home_score < r.away_score)
    return h, d, a


def _smoothed_vector(h: int, d: int, a: int) -> tuple[float, float, float]:
    total = h + d + a + 3 * ALPHA_SMOOTHING
    return (
        (h + ALPHA_SMOOTHING) / total,
        (d + ALPHA_SMOOTHING) / total,
        (a + ALPHA_SMOOTHING) / total,
    )


def expanding_league_prior(
    records: list[ModelRecord], home_team: str, away_team: str
) -> Prediction:
    h, d, a = _outcome_counts(records)
    p_home, p_draw, p_away = _smoothed_vector(h, d, a)
    _validate_probabilities(p_home, p_draw, p_away)
    return Prediction(
        p_home, p_draw, p_away, training_n=len(records), diagnostics={"h": h, "d": d, "a": a}
    )


def _rolling_window(
    records: list[ModelRecord], target: int = ROLLING_WINDOW_TARGET
) -> list[ModelRecord]:
    """`records` must already be sorted ascending by match_date. Returns the suffix
    covering at least `target` fixtures, rounded outward to whole match-date batches —
    never splitting a date's fixtures across the window boundary."""
    if len(records) <= target:
        return records
    counts: dict = {}
    for r in records:
        counts[r.match_date] = counts.get(r.match_date, 0) + 1
    dates_desc = list(reversed(counts))
    running = 0
    cutoff_date = dates_desc[-1]
    for d in dates_desc:
        running += counts[d]
        cutoff_date = d
        if running >= target:
            break
    return [r for r in records if r.match_date >= cutoff_date]


def rolling_league_frequency(
    records: list[ModelRecord], home_team: str, away_team: str
) -> Prediction:
    window = _rolling_window(records)
    h, d, a = _outcome_counts(window)
    p_home, p_draw, p_away = _smoothed_vector(h, d, a)
    _validate_probabilities(p_home, p_draw, p_away)
    return Prediction(
        p_home,
        p_draw,
        p_away,
        training_n=len(records),
        diagnostics={"h": h, "d": d, "a": a, "window_n": len(window)},
    )


def _league_means(records: list[ModelRecord]) -> tuple[float, float]:
    if not records:
        return LEAGUE_GOAL_MEAN_FALLBACK, LEAGUE_GOAL_MEAN_FALLBACK
    home_mean = sum(r.home_score for r in records) / len(records)
    away_mean = sum(r.away_score for r in records) / len(records)
    return home_mean, away_mean


@dataclass(frozen=True)
class _TeamRates:
    h_for: float
    h_conceded: float
    a_for: float
    a_conceded: float
    n_home: int
    n_away: int


def _team_rates(
    records: list[ModelRecord],
    team: str,
    league_home_mean: float,
    league_away_mean: float,
) -> _TeamRates:
    k = POISSON_SHRINKAGE_K
    home_matches = [r for r in records if r.home_team == team]
    away_matches = [r for r in records if r.away_team == team]
    n_home, n_away = len(home_matches), len(away_matches)

    sum_h_for = sum(r.home_score for r in home_matches)
    sum_h_conceded = sum(r.away_score for r in home_matches)
    sum_a_for = sum(r.away_score for r in away_matches)
    sum_a_conceded = sum(r.home_score for r in away_matches)

    return _TeamRates(
        h_for=(sum_h_for + k * league_home_mean) / (n_home + k),
        h_conceded=(sum_h_conceded + k * league_away_mean) / (n_home + k),
        a_for=(sum_a_for + k * league_away_mean) / (n_away + k),
        a_conceded=(sum_a_conceded + k * league_home_mean) / (n_away + k),
        n_home=n_home,
        n_away=n_away,
    )


def _poisson_pmf(lam: float, i: int) -> float:
    return math.exp(-lam) * lam**i / math.factorial(i)


def _validate_lambda(name: str, lam: float) -> None:
    if not math.isfinite(lam) or lam <= 0:
        raise BaselineModelError(f"{name} is not finite/positive: {lam}")


def poisson_goal_grid(
    lambda_home: float, lambda_away: float
) -> tuple[list[float], list[float], int, float, float]:
    """The SHARED independent-Poisson goal-grid / tail-bound construction, used by
    every model in this project that needs a joint goal-count distribution
    (`team_goal_poisson`, `league_only_poisson`, and S05's `dixon_coles_team_poisson`).
    Returns `(home_terms, away_terms, max_goals, included_mass, tail_mass)` — the raw,
    UN-aggregated per-goal-count probability lists, before any H/D/A aggregation and
    before any low-score correction is applied. This is intentionally public
    (no leading underscore) so a sibling module can reuse it without a second,
    divergently-maintained copy of the tail-bound search.
    """
    _validate_lambda("lambda_home", lambda_home)
    _validate_lambda("lambda_away", lambda_away)

    max_goals = 10
    home_terms: list[float] = []
    away_terms: list[float] = []
    included_mass = tail = 0.0
    while True:
        home_terms = [_poisson_pmf(lambda_home, i) for i in range(max_goals + 1)]
        away_terms = [_poisson_pmf(lambda_away, j) for j in range(max_goals + 1)]
        included_mass = sum(home_terms) * sum(away_terms)
        tail = 1.0 - included_mass
        if tail <= POISSON_TAIL_BOUND or max_goals >= POISSON_MAX_GOALS_CAP:
            break
        max_goals += 10

    if included_mass <= 0 or not math.isfinite(included_mass):
        raise BaselineModelError(f"included_mass is not usable: {included_mass}")

    return home_terms, away_terms, max_goals, included_mass, tail


def aggregate_joint_grid_to_1x2(
    home_terms: list[float],
    away_terms: list[float],
    cell_mass=lambda i, j, ph, pa: ph * pa,
) -> tuple[float, float, float, float]:
    """Aggregates a joint goal-count distribution into UNNORMALISED (h_mass, d_mass,
    a_mass, total_mass). `cell_mass(i, j, home_terms[i], away_terms[j])` computes each
    cell's joint mass — the plain independent-Poisson default is `ph * pa`; S05's
    Dixon-Coles challenger passes a callback that additionally multiplies the four
    low-score cells by `tau(i, j)` BEFORE this aggregation runs, never after. The
    caller divides by `total_mass` (re-summed here, not assumed) to get probabilities
    — this is the explicit renormalisation step the DC correction requires, and it is
    the SAME code path the plain Poisson models already used (where `total_mass`
    happens to equal the already-known `included_mass`).
    """
    h_mass = d_mass = a_mass = 0.0
    for i, ph in enumerate(home_terms):
        for j, pa in enumerate(away_terms):
            joint = cell_mass(i, j, ph, pa)
            if i > j:
                h_mass += joint
            elif i == j:
                d_mass += joint
            else:
                a_mass += joint
    return h_mass, d_mass, a_mass, h_mass + d_mass + a_mass


def _poisson_outcome_distribution(lambda_home: float, lambda_away: float) -> dict:
    """The SHARED goal-grid / tail-bound / H-D-A-aggregation routine used by BOTH
    plain-independent Poisson models (`team_goal_poisson` and `league_only_poisson`).
    Given the two independent Poisson rate parameters, returns a dict with the
    normalised `p_home`/`p_draw`/`p_away` plus the raw `tail_mass`/`included_mass`/
    `max_goals` diagnostics — never a second, divergent implementation.
    """
    home_terms, away_terms, max_goals, included_mass, tail = poisson_goal_grid(
        lambda_home, lambda_away
    )
    # Normalise by the already-known `included_mass` (= sum(home_terms) * sum(away_terms)),
    # NOT by re-summing h_mass+d_mass+a_mass from the aggregation loop below — the two are
    # mathematically equal but can differ in the last bit or two of floating-point
    # arithmetic, and this exact divisor is what S03/S04's frozen byte-identical output
    # was already computed with. Only S05's Dixon-Coles path (which genuinely changes the
    # total mass via tau) uses the freshly re-summed total from the aggregator.
    h_mass, d_mass, a_mass, _ = aggregate_joint_grid_to_1x2(home_terms, away_terms)
    p_home, p_draw, p_away = (
        h_mass / included_mass,
        d_mass / included_mass,
        a_mass / included_mass,
    )
    _validate_probabilities(p_home, p_draw, p_away)

    return {
        "p_home": p_home,
        "p_draw": p_draw,
        "p_away": p_away,
        "lambda_home": lambda_home,
        "lambda_away": lambda_away,
        "tail_mass": tail,
        "included_mass": included_mass,
        "max_goals": max_goals,
    }


def team_goal_poisson_lambdas(
    records: list[ModelRecord], home_team: str, away_team: str
) -> tuple[float, float, _TeamRates, _TeamRates]:
    """The exact pre-match lambda_home/lambda_away computation `team_goal_poisson`
    uses, extracted so S05's Dixon-Coles challenger (and this module's own cold-start
    diagnostics) can reuse the IDENTICAL team-rate/shrinkage logic without a second,
    divergent copy of it. Raises `BaselineModelError` on invalid league means — the
    exact same validation `team_goal_poisson` already performed inline.
    """
    league_home_mean, league_away_mean = _league_means(records)
    if not (math.isfinite(league_home_mean) and league_home_mean > 0):
        raise BaselineModelError(f"league_home_mean is not finite/positive: {league_home_mean}")
    if not (math.isfinite(league_away_mean) and league_away_mean > 0):
        raise BaselineModelError(f"league_away_mean is not finite/positive: {league_away_mean}")

    home_rates = _team_rates(records, home_team, league_home_mean, league_away_mean)
    away_rates = _team_rates(records, away_team, league_home_mean, league_away_mean)

    lambda_home = home_rates.h_for * away_rates.a_conceded / league_home_mean
    lambda_away = away_rates.a_for * home_rates.h_conceded / league_away_mean
    return lambda_home, lambda_away, home_rates, away_rates


def team_goal_poisson(records: list[ModelRecord], home_team: str, away_team: str) -> Prediction:
    lambda_home, lambda_away, home_rates, away_rates = team_goal_poisson_lambdas(
        records, home_team, away_team
    )

    dist = _poisson_outcome_distribution(lambda_home, lambda_away)
    trace = {k: v for k, v in dist.items() if k not in ("p_home", "p_draw", "p_away")}

    return Prediction(
        dist["p_home"],
        dist["p_draw"],
        dist["p_away"],
        training_n=len(records),
        diagnostics={
            **trace,
            "home_team_n_home": home_rates.n_home,
            "home_team_n_away": home_rates.n_away,
            "away_team_n_home": away_rates.n_home,
            "away_team_n_away": away_rates.n_away,
            "home_team_cold_start": (home_rates.n_home + home_rates.n_away) == 0,
            "away_team_cold_start": (away_rates.n_home + away_rates.n_away) == 0,
        },
    )


def league_only_poisson(records: list[ModelRecord], home_team: str, away_team: str) -> Prediction:
    """The S04 ablation: identical Poisson machinery (same goal-grid, tail-bound, k=5
    constants where applicable, and outcome-aggregation routine) as `team_goal_poisson`,
    but with NO team identity at all — `home_team`/`away_team` are accepted only to
    match the common model-function signature used by the backtest orchestrator and
    are never read. `lambda_home`/`lambda_away` are the plain league-wide home/away
    goal means (the same `_league_means` helper and the same safe 1.5/1.5 fallback on
    an empty training set as `team_goal_poisson` already uses) — never any
    team-specific rate. This isolates how much of `team_goal_poisson`'s advantage over
    the categorical baselines is attributable to the Poisson/goal-based likelihood
    family itself, versus to using team-specific attack/defence information on top of
    it (see docs/S04_ATTRIBUTION_AND_CALIBRATION... / reports/S04_ATTRIBUTION_AUDIT.md).
    """
    del home_team, away_team  # deliberately unused — this model has no team identity
    league_home_mean, league_away_mean = _league_means(records)
    if not (math.isfinite(league_home_mean) and league_home_mean > 0):
        raise BaselineModelError(f"league_home_mean is not finite/positive: {league_home_mean}")
    if not (math.isfinite(league_away_mean) and league_away_mean > 0):
        raise BaselineModelError(f"league_away_mean is not finite/positive: {league_away_mean}")

    dist = _poisson_outcome_distribution(league_home_mean, league_away_mean)
    trace = {k: v for k, v in dist.items() if k not in ("p_home", "p_draw", "p_away")}

    return Prediction(
        dist["p_home"],
        dist["p_draw"],
        dist["p_away"],
        training_n=len(records),
        diagnostics=trace,
    )

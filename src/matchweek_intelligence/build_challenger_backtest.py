"""The S05 five-model challenger backtest: the four frozen S04 models PLUS
`dixon_coles_team_poisson`, over the identical 760 held-out fixtures.

The four old models' rows are produced by literally calling
`build_attribution_backtest.run_attribution_backtest` and copying its output — never
a second, re-derived implementation of them — so their CSV fields are guaranteed
identical to their frozen S04 counterparts for the same fixture key, not merely
"close." Only `dixon_coles_team_poisson`'s rows are newly computed here.

Writes to NEW paths only: `reports/s05_challenger_metrics.json`,
`reports/s05_rho_fit_audit.json`, `data/processed/s05_challenger_predictions_REVIEW.csv`.
Never touches any S03 or S04 output.
"""

from __future__ import annotations

import csv
import json
import random
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

from matchweek_intelligence import metrics as mx
from matchweek_intelligence.baseline_models import BaselineModelError, team_goal_poisson_lambdas
from matchweek_intelligence.build_attribution_backtest import (
    EVALUATION_SEASONS,
    TRAINING_ONLY_SEASONS,
    AttributionPredictionRow,
    run_attribution_backtest,
)
from matchweek_intelligence.chronology import completed_training_results_as_of
from matchweek_intelligence.dixon_coles import (
    BOUNDARY_EPSILON,
    GOLDEN_SECTION_MAX_ITERATIONS,
    GOLDEN_SECTION_TOLERANCE,
    MIN_TRAINING_OBSERVATIONS_FOR_FIT,
    POSITIVITY_MARGIN,
    RHO_OUTER_BOUND,
    dixon_coles_outcome_distribution,
    fit_rho,
)
from matchweek_intelligence.fetch import PINNED_COMMIT, SOURCE_REPO
from matchweek_intelligence.model_inputs import ModelRecord, load_eligible_historical_records
from matchweek_intelligence.prediction_row_validation import validate_prediction_rows

DC_MODEL_NAME = "dixon_coles_team_poisson"
ALL_MODEL_NAMES = (
    "expanding_league_prior",
    "rolling_league_frequency",
    "team_goal_poisson",
    "league_only_poisson",
    DC_MODEL_NAME,
)

BOOTSTRAP_SEED = 20250103
BOOTSTRAP_REPLICATES = 1000

DEFAULT_METRICS_PATH = Path("reports/s05_challenger_metrics.json")
DEFAULT_RHO_AUDIT_PATH = Path("reports/s05_rho_fit_audit.json")
DEFAULT_PREDICTIONS_CSV_PATH = Path("data/processed/s05_challenger_predictions_REVIEW.csv")


class ChallengerBacktestError(RuntimeError):
    """Raised when the S05 backtest cannot be safely run or produced an invalid result."""


def _fixture_key(r) -> tuple:
    return (r.match_date, r.home_team, r.away_team)


@dataclass(frozen=True)
class ChallengerPredictionRow:
    match_date: str
    season: str
    home_team: str
    away_team: str
    home_score: int
    away_score: int
    actual_outcome: str
    model_name: str
    p_home: float
    p_draw: float
    p_away: float
    training_n: int
    latest_training_match_date: str
    home_team_exposure: int
    away_team_exposure: int
    home_team_cold_start: bool
    away_team_cold_start: bool
    log_loss: float
    brier: float
    rps: float
    accuracy_hit: bool
    lambda_home: str
    lambda_away: str
    included_mass: str
    tail_mass: str
    max_goals: str
    # New S05 trace columns — populated only for dixon_coles_team_poisson rows;
    # blank ("") for every other model, including the other two Poisson models,
    # which have no rho at all.
    rho: str
    rho_fit_status: str
    rho_fit_n: str
    rho_bound_lo: str
    rho_bound_hi: str


def _from_attribution_row(r: AttributionPredictionRow) -> ChallengerPredictionRow:
    return ChallengerPredictionRow(
        **r.__dict__,
        rho="",
        rho_fit_status="",
        rho_fit_n="",
        rho_bound_lo="",
        rho_bound_hi="",
    )


def _build_prequential_lambda_cache(
    all_records: list[ModelRecord],
) -> dict[tuple, tuple[float, float]]:
    """Computes, for EVERY scored match in the eligible corpus, its own pre-match
    (lambda_home, lambda_away) pair using results STRICTLY before that match's own
    date — never the match's own result, never anything dated on or after it. This
    is computed exactly once per match and cached, since a match's own pre-match
    lambda pair never depends on which LATER evaluation date is being predicted at
    the time it's used as a training observation (see docs/S05_DIXON_COLES_PROTOCOL.md).

    A small number of the earliest 2023/24 matches have too little prior history for
    `team_goal_poisson`'s own existing validation to produce a usable league mean
    (see the protocol doc's addendum) — those matches are simply omitted from the
    cache and therefore never contribute a training observation to any rho fit. This
    never affects the CURRENT fixture being predicted on any evaluation date, whose
    own lambda is always computed fresh from that date's full (never-degenerate)
    training set.
    """
    cache: dict[tuple, tuple[float, float]] = {}
    for r in sorted(all_records, key=lambda rec: (rec.match_date, rec.home_team, rec.away_team)):
        training_before = completed_training_results_as_of(all_records, r.match_date)
        try:
            lambda_home, lambda_away, _, _ = team_goal_poisson_lambdas(
                training_before, r.home_team, r.away_team
            )
        except BaselineModelError:
            continue
        cache[_fixture_key(r)] = (lambda_home, lambda_away)
    return cache


def run_challenger_backtest(
    all_records: list[ModelRecord] | None = None,
) -> tuple[list[ChallengerPredictionRow], list[dict]]:
    all_records = all_records if all_records is not None else load_eligible_historical_records()

    if any(r.season == "2026-27" for r in all_records):
        raise ChallengerBacktestError("2026/27 must never appear in the model-input corpus")

    old_rows = run_attribution_backtest(all_records=all_records)  # validated internally
    rows: list[ChallengerPredictionRow] = [_from_attribution_row(r) for r in old_rows]

    eval_records = [r for r in all_records if r.season in EVALUATION_SEASONS]
    if len(eval_records) != 760:
        raise ChallengerBacktestError(
            f"expected 760 evaluation fixtures, found {len(eval_records)}"
        )

    lambda_cache = _build_prequential_lambda_cache(all_records)
    eval_dates = sorted({r.match_date for r in eval_records})
    rho_audit: list[dict] = []

    for d in eval_dates:
        training = completed_training_results_as_of(all_records, d)
        if any(r.match_date >= d for r in training):
            raise ChallengerBacktestError(f"leakage: training set for {d} contains a same-day+ row")
        latest_training_date = max((r.match_date for r in training), default=None)

        training_observations = [
            (r.home_score, r.away_score, *lambda_cache[_fixture_key(r)])
            for r in training
            if _fixture_key(r) in lambda_cache
        ]

        fixtures_on_day = [r for r in eval_records if r.match_date == d]
        today_lambda_pairs: list[tuple[float, float]] = []
        for fixture in fixtures_on_day:
            lh, la, _, _ = team_goal_poisson_lambdas(training, fixture.home_team, fixture.away_team)
            today_lambda_pairs.append((lh, la))

        fit_result = fit_rho(training_observations, today_lambda_pairs)
        rho_audit.append(
            {
                "match_date": d.isoformat(),
                "rho": fit_result.rho,
                "fit_status": fit_result.fit_status,
                "n_training": fit_result.n_training,
                "bound_lo": fit_result.bound_lo,
                "bound_hi": fit_result.bound_hi,
                "n_fixtures_this_date": len(fixtures_on_day),
            }
        )

        for fixture, (lh, la) in zip(fixtures_on_day, today_lambda_pairs, strict=True):
            actual = (
                "H"
                if fixture.home_score > fixture.away_score
                else ("D" if fixture.home_score == fixture.away_score else "A")
            )
            home_exposure = sum(
                1
                for r in training
                if r.home_team == fixture.home_team or r.away_team == fixture.home_team
            )
            away_exposure = sum(
                1
                for r in training
                if r.home_team == fixture.away_team or r.away_team == fixture.away_team
            )
            dist = dixon_coles_outcome_distribution(lh, la, fit_result.rho)
            p_map = {"H": dist["p_home"], "D": dist["p_draw"], "A": dist["p_away"]}

            rows.append(
                ChallengerPredictionRow(
                    match_date=d.isoformat(),
                    season=fixture.season,
                    home_team=fixture.home_team,
                    away_team=fixture.away_team,
                    home_score=fixture.home_score,
                    away_score=fixture.away_score,
                    actual_outcome=actual,
                    model_name=DC_MODEL_NAME,
                    p_home=dist["p_home"],
                    p_draw=dist["p_draw"],
                    p_away=dist["p_away"],
                    training_n=len(training),
                    latest_training_match_date=(
                        latest_training_date.isoformat() if latest_training_date else ""
                    ),
                    home_team_exposure=home_exposure,
                    away_team_exposure=away_exposure,
                    home_team_cold_start=home_exposure == 0,
                    away_team_cold_start=away_exposure == 0,
                    log_loss=mx.log_loss(p_map[actual]),
                    brier=mx.brier_score(dist["p_home"], dist["p_draw"], dist["p_away"], actual),
                    rps=mx.ranked_probability_score(
                        dist["p_home"], dist["p_draw"], dist["p_away"], actual
                    ),
                    accuracy_hit=mx.top_class_accuracy_hit(
                        dist["p_home"], dist["p_draw"], dist["p_away"], actual
                    ),
                    lambda_home=str(dist["lambda_home"]),
                    lambda_away=str(dist["lambda_away"]),
                    included_mass=str(dist["included_mass"]),
                    tail_mass=str(dist["tail_mass"]),
                    max_goals=str(dist["max_goals"]),
                    rho=str(fit_result.rho),
                    rho_fit_status=fit_result.fit_status,
                    rho_fit_n=str(fit_result.n_training),
                    rho_bound_lo=str(fit_result.bound_lo)
                    if fit_result.bound_lo is not None
                    else "",
                    rho_bound_hi=str(fit_result.bound_hi)
                    if fit_result.bound_hi is not None
                    else "",
                )
            )

    dc_rows = [r for r in rows if r.model_name == DC_MODEL_NAME]
    if len(dc_rows) != 760:
        raise ChallengerBacktestError(f"{DC_MODEL_NAME}: expected 760 rows, found {len(dc_rows)}")
    for season in EVALUATION_SEASONS:
        n = sum(1 for r in dc_rows if r.season == season)
        if n != 380:
            raise ChallengerBacktestError(f"{DC_MODEL_NAME} {season}: expected 380, found {n}")

    return rows, rho_audit


def write_predictions_csv(
    rows: list[ChallengerPredictionRow], path: Path = DEFAULT_PREDICTIONS_CSV_PATH
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(ChallengerPredictionRow.__dataclass_fields__.keys())
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row.__dict__)


def write_rho_audit(rho_audit: list[dict], path: Path = DEFAULT_RHO_AUDIT_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rhos = [a["rho"] for a in rho_audit]
    status_counts: dict[str, int] = defaultdict(int)
    for a in rho_audit:
        status_counts[a["fit_status"]] += 1
    summary = {
        "n_dates": len(rho_audit),
        "rho_min": min(rhos),
        "rho_median": sorted(rhos)[len(rhos) // 2],
        "rho_max": max(rhos),
        "fit_status_counts": dict(status_counts),
        "entries": rho_audit,
    }
    path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _aggregate(
    rows: list[ChallengerPredictionRow], model_name: str, season: str | None = None
) -> dict:
    subset = [
        r for r in rows if r.model_name == model_name and (season is None or r.season == season)
    ]
    n = len(subset)
    if n == 0:
        raise ChallengerBacktestError(f"no rows for model={model_name} season={season}")
    return {
        "n": n,
        "log_loss": sum(r.log_loss for r in subset) / n,
        "brier": sum(r.brier for r in subset) / n,
        "rps": sum(r.rps for r in subset) / n,
        "accuracy": sum(1 for r in subset if r.accuracy_hit) / n,
    }


def _date_block_bootstrap_log_loss_diff(
    rows: list[ChallengerPredictionRow],
    model_left: str,
    model_right: str,
    season: str | None,
    seed: int = BOOTSTRAP_SEED,
    replicates: int = BOOTSTRAP_REPLICATES,
) -> dict:
    by_date_left: dict[str, list[float]] = defaultdict(list)
    by_date_right: dict[str, list[float]] = defaultdict(list)
    for r in rows:
        if season is not None and r.season != season:
            continue
        if r.model_name == model_left:
            by_date_left[r.match_date].append(r.log_loss)
        elif r.model_name == model_right:
            by_date_right[r.match_date].append(r.log_loss)

    dates = sorted(by_date_left.keys())
    if not dates or sorted(by_date_right.keys()) != dates:
        raise ChallengerBacktestError("mismatched date sets between models for bootstrap")

    point_diff = (
        sum(sum(v) for v in by_date_right.values()) / sum(len(v) for v in by_date_right.values())
    ) - (sum(sum(v) for v in by_date_left.values()) / sum(len(v) for v in by_date_left.values()))

    rng = random.Random(seed)
    diffs = []
    for _ in range(replicates):
        sample_dates = [rng.choice(dates) for _ in dates]
        left_vals = [v for dd in sample_dates for v in by_date_left[dd]]
        right_vals = [v for dd in sample_dates for v in by_date_right[dd]]
        diffs.append(sum(right_vals) / len(right_vals) - sum(left_vals) / len(left_vals))
    diffs.sort()
    lo = diffs[int(0.025 * replicates)]
    hi = diffs[min(int(0.975 * replicates), replicates - 1)]
    return {
        "left_model": model_left,
        "right_model": model_right,
        "point_diff_log_loss_right_minus_left": point_diff,
        "ci95_descriptive": [lo, hi],
        # point_diff = mean(right) - mean(left): NEGATIVE means right_model's log loss
        # is LOWER, i.e. right_model wins. (Corrected in S06 — this previously read
        # "negative means left_model wins", which is backwards; reproduced with a
        # synthetic exact-log-loss pair before this fix. The written prose conclusions
        # in reports/S05_DIXON_COLES_EVALUATION.md were already correct; only this
        # machine-readable field was wrong.)
        "interpretation": "negative means right_model wins (lower log loss)",
        "replicates": replicates,
        "seed": seed,
        "note": "descriptive and approximate; not a formal hypothesis test",
    }


def _draw_calibration(rows: list[ChallengerPredictionRow], model_name: str) -> dict:
    subset = [r for r in rows if r.model_name == model_name]
    n = len(subset)
    mean_pred = sum(r.p_draw for r in subset) / n
    observed = sum(1 for r in subset if r.actual_outcome == "D") / n
    return {
        "n": n,
        "mean_predicted_pct": mean_pred * 100,
        "observed_pct": observed * 100,
        "gap_pct_points_observed_minus_predicted": (observed - mean_pred) * 100,
    }


def _draw_calibration_bins(
    rows: list[ChallengerPredictionRow], model_name: str, n_bins: int = 5
) -> list[dict]:
    subset = [r for r in rows if r.model_name == model_name]
    ordered = sorted(subset, key=lambda r: (r.p_draw, _fixture_key(r)))
    n = len(ordered)
    if n < n_bins:
        return []
    base, remainder = divmod(n, n_bins)
    bins = []
    start = 0
    for i in range(n_bins):
        size = base + (1 if i < remainder else 0)
        chunk = ordered[start : start + size]
        start += size
        mean_pred = sum(r.p_draw for r in chunk) / len(chunk)
        observed = sum(1 for r in chunk if r.actual_outcome == "D") / len(chunk)
        bins.append(
            {
                "bin_index": i,
                "n": len(chunk),
                "mean_predicted_pct": mean_pred * 100,
                "observed_rate_pct": observed * 100,
                "predicted_prob_range": [chunk[0].p_draw, chunk[-1].p_draw],
            }
        )
    return bins


def build_metrics_report(rows: list[ChallengerPredictionRow], rho_audit: list[dict]) -> dict:
    validate_prediction_rows(
        rows,
        expected_models=frozenset(ALL_MODEL_NAMES),
        expected_n_per_model=760,
        season_split={season: 380 for season in EVALUATION_SEASONS},
    )

    overall_by_model = {m: _aggregate(rows, m) for m in ALL_MODEL_NAMES}
    by_season = {
        season: {m: _aggregate(rows, m, season=season) for m in ALL_MODEL_NAMES}
        for season in EVALUATION_SEASONS
    }

    dc_vs_team = {
        "overall": _date_block_bootstrap_log_loss_diff(
            rows, "team_goal_poisson", DC_MODEL_NAME, season=None
        ),
        "by_season": {
            season: _date_block_bootstrap_log_loss_diff(
                rows, "team_goal_poisson", DC_MODEL_NAME, season=season
            )
            for season in EVALUATION_SEASONS
        },
    }

    draw_calibration = {m: _draw_calibration(rows, m) for m in ALL_MODEL_NAMES}
    draw_bins = {m: _draw_calibration_bins(rows, m) for m in ALL_MODEL_NAMES}

    rhos = [a["rho"] for a in rho_audit]
    status_counts: dict[str, int] = defaultdict(int)
    for a in rho_audit:
        status_counts[a["fit_status"]] += 1

    overall_diff = dc_vs_team["overall"]
    point_diff = overall_diff["point_diff_log_loss_right_minus_left"]
    ci_lo, ci_hi = overall_diff["ci95_descriptive"]
    if point_diff >= 0:
        recommendation = (
            "dixon_coles_team_poisson does NOT improve log loss over frozen team_goal_poisson "
            "in this replay (point estimate is non-negative) — recommend keeping "
            "team_goal_poisson as the default."
        )
    elif ci_hi < 0:
        recommendation = (
            "dixon_coles_team_poisson shows a log-loss improvement over frozen "
            "team_goal_poisson whose 95% descriptive interval excludes zero in this replay — "
            "a real, though still exploratory and hindsight-informed, result. See "
            "reports/S05_DIXON_COLES_EVALUATION.md for the full adoption discussion before "
            "treating this as a decision to switch the default."
        )
    else:
        recommendation = (
            "dixon_coles_team_poisson's point-estimate log loss is slightly better than frozen "
            "team_goal_poisson's in this replay, but the 95% descriptive interval straddles "
            "zero — this is NOT strong enough evidence to confidently adopt the added "
            "complexity. Recommend keeping team_goal_poisson as the public demo's forecasting "
            "default; dixon_coles_team_poisson remains a documented, promising candidate for "
            "a future genuinely prospective test, not a replacement earned by this replay alone."
        )

    return {
        "source_repo": SOURCE_REPO,
        "pinned_commit": PINNED_COMMIT,
        "training_only_seasons": list(TRAINING_ONLY_SEASONS),
        "evaluation_seasons": list(EVALUATION_SEASONS),
        "total_evaluation_n": len(rows) // len(ALL_MODEL_NAMES),
        "hindsight_disclosure": (
            "Both evaluated seasons have already been inspected repeatedly across S03/S04/S05. "
            "This is an exploratory, hindsight-informed chronological replay, not a pristine "
            "prospective holdout. See docs/S05_DIXON_COLES_PROTOCOL.md."
        ),
        "config": {
            "rho_outer_bound": list(RHO_OUTER_BOUND),
            "positivity_margin": POSITIVITY_MARGIN,
            "golden_section_max_iterations": GOLDEN_SECTION_MAX_ITERATIONS,
            "golden_section_tolerance": GOLDEN_SECTION_TOLERANCE,
            "min_training_observations_for_fit": MIN_TRAINING_OBSERVATIONS_FOR_FIT,
            "boundary_epsilon": BOUNDARY_EPSILON,
            "bootstrap": {
                "method": "paired fixed-seed date-block bootstrap",
                "seed": BOOTSTRAP_SEED,
                "replicates": BOOTSTRAP_REPLICATES,
            },
        },
        "models": {"overall": overall_by_model, "by_season": by_season},
        "dixon_coles_vs_team_goal_poisson": dc_vs_team,
        "draw_calibration": draw_calibration,
        "draw_calibration_bins": draw_bins,
        "rho_summary": {
            "n_dates": len(rho_audit),
            "rho_min": min(rhos),
            "rho_median": sorted(rhos)[len(rhos) // 2],
            "rho_max": max(rhos),
            "fit_status_counts": dict(status_counts),
        },
        "adoption_recommendation": recommendation,
    }


def write_metrics_report(report: dict, path: Path = DEFAULT_METRICS_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> None:
    rows, rho_audit = run_challenger_backtest()
    report = build_metrics_report(rows, rho_audit)  # validates before any write below
    write_predictions_csv(rows)
    write_rho_audit(rho_audit)
    write_metrics_report(report)
    print(f"evaluated {report['total_evaluation_n']} fixtures across {len(ALL_MODEL_NAMES)} models")
    for model, agg in report["models"]["overall"].items():
        ll, br, rp = agg["log_loss"], agg["brier"], agg["rps"]
        print(f"  {model}: log_loss={ll:.4f} brier={br:.4f} rps={rp:.4f}")
    print(report["adoption_recommendation"])


if __name__ == "__main__":
    main()

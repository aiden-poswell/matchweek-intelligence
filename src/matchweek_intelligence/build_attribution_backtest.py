"""The S04 four-model attribution backtest: the original three S03 baselines PLUS the
new `league_only_poisson` ablation, over the identical 760 held-out fixtures.

This module writes to NEW paths only (`reports/s04_attribution_metrics.json`,
`data/processed/s04_ablation_predictions_REVIEW.csv`) — it never reads, writes, or
touches `reports/s03_baseline_backtest_metrics.json` or
`data/processed/s03_backtest_predictions_REVIEW.csv`, which remain exactly as S03 left
them. The walk-forward chronology (one training set per evaluation date, built via
`chronology.completed_training_results_as_of`, identical rules as S03) is intentionally
re-implemented here rather than imported from `build_baseline_backtest.py`, so that
module's frozen behaviour is not put at any risk of being refactored out from under it.
"""

from __future__ import annotations

import csv
import json
import random
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

from matchweek_intelligence import baseline_models as bm
from matchweek_intelligence import metrics as mx
from matchweek_intelligence.chronology import completed_training_results_as_of
from matchweek_intelligence.fetch import PINNED_COMMIT, SOURCE_REPO
from matchweek_intelligence.model_inputs import ModelRecord, load_eligible_historical_records
from matchweek_intelligence.prediction_row_validation import validate_prediction_rows

EVALUATION_SEASONS: tuple[str, ...] = ("2024-25", "2025-26")
TRAINING_ONLY_SEASONS: tuple[str, ...] = ("2023-24",)

BOOTSTRAP_SEED = 20250103
BOOTSTRAP_REPLICATES = 1000

DEFAULT_METRICS_PATH = Path("reports/s04_attribution_metrics.json")
DEFAULT_PREDICTIONS_CSV_PATH = Path("data/processed/s04_ablation_predictions_REVIEW.csv")

# Order matters for readability only; the backtest treats all four identically.
_MODELS = {
    "expanding_league_prior": bm.expanding_league_prior,
    "rolling_league_frequency": bm.rolling_league_frequency,
    "team_goal_poisson": bm.team_goal_poisson,
    "league_only_poisson": bm.league_only_poisson,
}
_POISSON_MODELS = frozenset({"team_goal_poisson", "league_only_poisson"})


class AttributionBacktestError(RuntimeError):
    """Raised when the S04 backtest cannot be safely run or produced an invalid result."""


def _actual_outcome(r: ModelRecord) -> str:
    if r.home_score > r.away_score:
        return "H"
    if r.home_score == r.away_score:
        return "D"
    return "A"


def _exposure(training: list[ModelRecord], team: str) -> int:
    return sum(1 for r in training if r.home_team == team or r.away_team == team)


@dataclass(frozen=True)
class AttributionPredictionRow:
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
    # New S04 trace columns — populated only for the two Poisson models; blank ("")
    # for the two categorical baselines, which have no goal-rate parameters at all.
    lambda_home: str
    lambda_away: str
    included_mass: str
    tail_mass: str
    max_goals: str


def run_attribution_backtest(
    all_records: list[ModelRecord] | None = None,
) -> list[AttributionPredictionRow]:
    all_records = all_records if all_records is not None else load_eligible_historical_records()

    if any(r.season == "2026-27" for r in all_records):
        raise AttributionBacktestError("2026/27 must never appear in the model-input corpus")

    eval_records = [r for r in all_records if r.season in EVALUATION_SEASONS]
    if len(eval_records) != 760:
        raise AttributionBacktestError(
            f"expected 760 evaluation fixtures (380 per season), found {len(eval_records)}"
        )
    for season in EVALUATION_SEASONS:
        n = sum(1 for r in eval_records if r.season == season)
        if n != 380:
            raise AttributionBacktestError(f"season {season}: expected 380 fixtures, found {n}")

    eval_dates = sorted({r.match_date for r in eval_records})
    rows: list[AttributionPredictionRow] = []

    for d in eval_dates:
        training = completed_training_results_as_of(all_records, d)
        if any(r.match_date >= d for r in training):
            raise AttributionBacktestError(
                f"leakage: training set for {d} contains a same-day+ row"
            )
        latest_training_date = max((r.match_date for r in training), default=None)

        fixtures_on_day = [r for r in eval_records if r.match_date == d]
        for fixture in fixtures_on_day:
            actual = _actual_outcome(fixture)
            home_exposure = _exposure(training, fixture.home_team)
            away_exposure = _exposure(training, fixture.away_team)
            for model_name, model_fn in _MODELS.items():
                pred = model_fn(training, fixture.home_team, fixture.away_team)
                p_map = {"H": pred.p_home, "D": pred.p_draw, "A": pred.p_away}
                is_poisson = model_name in _POISSON_MODELS
                rows.append(
                    AttributionPredictionRow(
                        match_date=d.isoformat(),
                        season=fixture.season,
                        home_team=fixture.home_team,
                        away_team=fixture.away_team,
                        home_score=fixture.home_score,
                        away_score=fixture.away_score,
                        actual_outcome=actual,
                        model_name=model_name,
                        p_home=pred.p_home,
                        p_draw=pred.p_draw,
                        p_away=pred.p_away,
                        training_n=pred.training_n,
                        latest_training_match_date=(
                            latest_training_date.isoformat() if latest_training_date else ""
                        ),
                        home_team_exposure=home_exposure,
                        away_team_exposure=away_exposure,
                        home_team_cold_start=home_exposure == 0,
                        away_team_cold_start=away_exposure == 0,
                        log_loss=mx.log_loss(p_map[actual]),
                        brier=mx.brier_score(pred.p_home, pred.p_draw, pred.p_away, actual),
                        rps=mx.ranked_probability_score(
                            pred.p_home, pred.p_draw, pred.p_away, actual
                        ),
                        accuracy_hit=mx.top_class_accuracy_hit(
                            pred.p_home, pred.p_draw, pred.p_away, actual
                        ),
                        lambda_home=str(pred.diagnostics["lambda_home"]) if is_poisson else "",
                        lambda_away=str(pred.diagnostics["lambda_away"]) if is_poisson else "",
                        included_mass=(
                            str(pred.diagnostics["included_mass"]) if is_poisson else ""
                        ),
                        tail_mass=str(pred.diagnostics["tail_mass"]) if is_poisson else "",
                        max_goals=str(pred.diagnostics["max_goals"]) if is_poisson else "",
                    )
                )
    return rows


def write_predictions_csv(
    rows: list[AttributionPredictionRow], path: Path = DEFAULT_PREDICTIONS_CSV_PATH
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(AttributionPredictionRow.__dataclass_fields__.keys())
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row.__dict__)


def _aggregate(
    rows: list[AttributionPredictionRow], model_name: str, season: str | None = None
) -> dict:
    subset = [
        r for r in rows if r.model_name == model_name and (season is None or r.season == season)
    ]
    n = len(subset)
    if n == 0:
        raise AttributionBacktestError(f"no rows for model={model_name} season={season}")
    return {
        "n": n,
        "log_loss": sum(r.log_loss for r in subset) / n,
        "brier": sum(r.brier for r in subset) / n,
        "rps": sum(r.rps for r in subset) / n,
        "accuracy": sum(1 for r in subset if r.accuracy_hit) / n,
    }


def _date_block_bootstrap_log_loss_diff(
    rows: list[AttributionPredictionRow],
    model_left: str,
    model_right: str,
    season: str | None,
    seed: int = BOOTSTRAP_SEED,
    replicates: int = BOOTSTRAP_REPLICATES,
) -> dict:
    """95% descriptive (not inferential) interval for mean log-loss(model_right) -
    mean log-loss(model_left); negative means model_right wins (lower log loss).
    Resamples whole evaluation dates with replacement, the SAME resampled date list
    applied to both models each replicate."""
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
        raise AttributionBacktestError("mismatched date sets between models for bootstrap")

    point_diff = (
        sum(sum(v) for v in by_date_right.values()) / sum(len(v) for v in by_date_right.values())
    ) - (sum(sum(v) for v in by_date_left.values()) / sum(len(v) for v in by_date_left.values()))

    rng = random.Random(seed)
    diffs = []
    for _ in range(replicates):
        sample_dates = [rng.choice(dates) for _ in dates]
        left_vals = [v for d in sample_dates for v in by_date_left[d]]
        right_vals = [v for d in sample_dates for v in by_date_right[d]]
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
        # is LOWER, i.e. right_model wins. (S07 erratum — this previously read
        # "negative means left_model wins", which is backwards; reproduced with a
        # synthetic exact-log-loss pair before this fix. See
        # reports/S07_S04_INTERPRETATION_ERRATUM.md.)
        "interpretation": "negative means right_model wins (lower log loss)",
        "replicates": replicates,
        "seed": seed,
        "note": "descriptive and approximate; not a formal hypothesis test",
    }


def build_metrics_report(rows: list[AttributionPredictionRow]) -> dict:
    models = list(_MODELS.keys())
    # Never trust the supplied rows' fields — including the precomputed log_loss/brier/
    # rps/accuracy_hit columns — without independently re-verifying them first. See
    # prediction_row_validation.py's module docstring for the real defect this closes.
    validate_prediction_rows(
        rows,
        expected_models=frozenset(models),
        expected_n_per_model=760,
        season_split={season: 380 for season in EVALUATION_SEASONS},
    )
    overall_by_model = {m: _aggregate(rows, m) for m in models}
    by_season = {
        season: {m: _aggregate(rows, m, season=season) for m in models}
        for season in EVALUATION_SEASONS
    }

    comparisons = {
        "team_goal_poisson_minus_league_only_poisson": {
            "overall": _date_block_bootstrap_log_loss_diff(
                rows, "league_only_poisson", "team_goal_poisson", season=None
            ),
            "by_season": {
                season: _date_block_bootstrap_log_loss_diff(
                    rows, "league_only_poisson", "team_goal_poisson", season=season
                )
                for season in EVALUATION_SEASONS
            },
        },
        "league_only_poisson_minus_expanding_league_prior": {
            "overall": _date_block_bootstrap_log_loss_diff(
                rows, "expanding_league_prior", "league_only_poisson", season=None
            ),
            "by_season": {
                season: _date_block_bootstrap_log_loss_diff(
                    rows, "expanding_league_prior", "league_only_poisson", season=season
                )
                for season in EVALUATION_SEASONS
            },
        },
    }

    return {
        "source_repo": SOURCE_REPO,
        "pinned_commit": PINNED_COMMIT,
        "training_only_seasons": list(TRAINING_ONLY_SEASONS),
        "evaluation_seasons": list(EVALUATION_SEASONS),
        "total_evaluation_n": len(rows) // len(models),
        "config": {
            "cutoff_policy": (
                "chronology.completed_training_results_as_of(all_eligible_historical_records, d): "
                "status == 'played_with_score' AND match_date < d, strictly; same-day fixtures "
                "are always excluded as a whole batch, never partially included"
            ),
            "alpha_smoothing": bm.ALPHA_SMOOTHING,
            "rolling_window_target": bm.ROLLING_WINDOW_TARGET,
            "poisson_shrinkage_k": bm.POISSON_SHRINKAGE_K,
            "poisson_tail_bound": bm.POISSON_TAIL_BOUND,
            "league_goal_mean_fallback": bm.LEAGUE_GOAL_MEAN_FALLBACK,
            "scoring_convention": {
                "outcome_order": list(mx.OUTCOME_ORDER),
                "brier": "three-component sum-of-squared-errors (range [0,2])",
                "rps": "cumulative at H|D boundary, divided by 2",
            },
            "bootstrap": {
                "method": "paired fixed-seed date-block bootstrap",
                "seed": BOOTSTRAP_SEED,
                "replicates": BOOTSTRAP_REPLICATES,
            },
            "ablation_note": (
                "league_only_poisson shares the exact goal-grid/tail-bound/outcome-aggregation "
                "routine with team_goal_poisson (baseline_models._poisson_outcome_distribution); "
                "it differs ONLY in using plain league-wide goal means as lambda instead of "
                "team-specific shrunk rates — isolating the Poisson-likelihood-family effect "
                "from the team-identity effect"
            ),
        },
        "models": {
            "overall": overall_by_model,
            "by_season": by_season,
        },
        "attribution_comparison": comparisons,
    }


def write_metrics_report(report: dict, path: Path = DEFAULT_METRICS_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> None:
    rows = run_attribution_backtest()
    # Validate BEFORE writing anything: build_metrics_report's internal validation
    # must gate both output files, not just the metrics JSON — a prior version of
    # this function wrote the CSV before any validation ran at all.
    report = build_metrics_report(rows)
    write_predictions_csv(rows)
    write_metrics_report(report)
    print(f"evaluated {report['total_evaluation_n']} fixtures across {len(_MODELS)} models")
    for model, agg in report["models"]["overall"].items():
        ll, br, rp = agg["log_loss"], agg["brier"], agg["rps"]
        print(f"  {model}: log_loss={ll:.4f} brier={br:.4f} rps={rp:.4f}")
    tp = report["attribution_comparison"]["team_goal_poisson_minus_league_only_poisson"]["overall"]
    diff = tp["point_diff_log_loss_right_minus_left"]
    print(f"team_goal_poisson - league_only_poisson (overall log-loss diff): {diff:.4f}")


if __name__ == "__main__":
    main()

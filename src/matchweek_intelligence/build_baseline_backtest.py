"""The S03 out-of-time backtest: walk forward through the three eligible historical
seasons, predict every 2024/25 and 2025/26 fixture with each of the three predeclared
baselines (docs/S03_BASELINE_METHODS.md), score them, and write the deterministic
aggregate report, the metrics JSON, and the gitignored per-fixture review CSV.

Chronology is enforced structurally, not just by convention: every prediction for date
`d` is built from `chronology.completed_training_results_as_of(all_records, d)`, which
can never return a same-day or later row, and can never return a `result_missing` row.
2023/24 is training-only (never evaluated); 2026/27 is never loaded at all
(`model_inputs.ELIGIBLE_SEASONS` excludes it structurally).
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
from matchweek_intelligence.model_inputs import (
    ELIGIBLE_SEASONS,
    ModelRecord,
    load_eligible_historical_records,
)

EVALUATION_SEASONS: tuple[str, ...] = ("2024-25", "2025-26")
TRAINING_ONLY_SEASONS: tuple[str, ...] = tuple(
    s for s in ELIGIBLE_SEASONS if s not in EVALUATION_SEASONS
)

BOOTSTRAP_SEED = 20250103
BOOTSTRAP_REPLICATES = 1000

DEFAULT_METRICS_PATH = Path("reports/s03_baseline_backtest_metrics.json")
DEFAULT_REPORT_PATH = Path("reports/S03_BASELINE_BACKTEST.md")
DEFAULT_PREDICTIONS_CSV_PATH = Path("data/processed/s03_backtest_predictions_REVIEW.csv")

_MODELS = {
    "expanding_league_prior": bm.expanding_league_prior,
    "rolling_league_frequency": bm.rolling_league_frequency,
    "team_goal_poisson": bm.team_goal_poisson,
}


class BaselineBacktestError(RuntimeError):
    """Raised when the backtest cannot be safely run or produced an invalid result."""


def _actual_outcome(r: ModelRecord) -> str:
    if r.home_score > r.away_score:
        return "H"
    if r.home_score == r.away_score:
        return "D"
    return "A"


@dataclass(frozen=True)
class PredictionRow:
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


def _exposure(training: list[ModelRecord], team: str) -> int:
    return sum(1 for r in training if r.home_team == team or r.away_team == team)


def run_backtest(all_records: list[ModelRecord] | None = None) -> list[PredictionRow]:
    all_records = all_records if all_records is not None else load_eligible_historical_records()

    # The 2026/27 exclusion is checked first, as the most fundamental invariant: this
    # must never pass simply because some OTHER count happens to fail first.
    if any(r.season == "2026-27" for r in all_records):
        raise BaselineBacktestError("2026/27 must never appear in the model-input corpus")

    eval_records = [r for r in all_records if r.season in EVALUATION_SEASONS]
    if len(eval_records) != 760:
        raise BaselineBacktestError(
            f"expected 760 evaluation fixtures (380 per season), found {len(eval_records)}"
        )
    for season in EVALUATION_SEASONS:
        n = sum(1 for r in eval_records if r.season == season)
        if n != 380:
            raise BaselineBacktestError(f"season {season}: expected 380 fixtures, found {n}")

    eval_dates = sorted({r.match_date for r in eval_records})
    rows: list[PredictionRow] = []

    for d in eval_dates:
        training = completed_training_results_as_of(all_records, d)
        if any(r.match_date >= d for r in training):
            raise BaselineBacktestError(f"leakage: training set for {d} contains a same-day+ row")
        latest_training_date = max((r.match_date for r in training), default=None)

        fixtures_on_day = [r for r in eval_records if r.match_date == d]
        for fixture in fixtures_on_day:
            actual = _actual_outcome(fixture)
            home_exposure = _exposure(training, fixture.home_team)
            away_exposure = _exposure(training, fixture.away_team)
            for model_name, model_fn in _MODELS.items():
                pred = model_fn(training, fixture.home_team, fixture.away_team)
                p_map = {"H": pred.p_home, "D": pred.p_draw, "A": pred.p_away}
                rows.append(
                    PredictionRow(
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
                    )
                )
    return rows


def write_predictions_csv(
    rows: list[PredictionRow], path: Path = DEFAULT_PREDICTIONS_CSV_PATH
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(PredictionRow.__dataclass_fields__.keys())
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row.__dict__)


def _aggregate(rows: list[PredictionRow], model_name: str, season: str | None = None) -> dict:
    subset = [
        r for r in rows if r.model_name == model_name and (season is None or r.season == season)
    ]
    n = len(subset)
    if n == 0:
        raise BaselineBacktestError(f"no rows for model={model_name} season={season}")
    return {
        "n": n,
        "log_loss": sum(r.log_loss for r in subset) / n,
        "brier": sum(r.brier for r in subset) / n,
        "rps": sum(r.rps for r in subset) / n,
        "accuracy": sum(1 for r in subset if r.accuracy_hit) / n,
    }


def _date_block_bootstrap_log_loss_diff(
    rows: list[PredictionRow],
    model_a: str,
    model_b: str,
    season: str | None,
    seed: int = BOOTSTRAP_SEED,
    replicates: int = BOOTSTRAP_REPLICATES,
) -> dict:
    """95% descriptive (not inferential) interval for mean log-loss(model_b) -
    mean log-loss(model_a), resampling whole evaluation dates with replacement, the
    SAME resampled date list applied to both models each replicate."""
    by_date_a: dict[str, list[float]] = defaultdict(list)
    by_date_b: dict[str, list[float]] = defaultdict(list)
    for r in rows:
        if season is not None and r.season != season:
            continue
        if r.model_name == model_a:
            by_date_a[r.match_date].append(r.log_loss)
        elif r.model_name == model_b:
            by_date_b[r.match_date].append(r.log_loss)

    dates = sorted(by_date_a.keys())
    if not dates or sorted(by_date_b.keys()) != dates:
        raise BaselineBacktestError("mismatched date sets between models for bootstrap")

    point_diff = (
        sum(sum(v) for v in by_date_b.values()) / sum(len(v) for v in by_date_b.values())
    ) - (sum(sum(v) for v in by_date_a.values()) / sum(len(v) for v in by_date_a.values()))

    rng = random.Random(seed)
    diffs = []
    for _ in range(replicates):
        sample_dates = [rng.choice(dates) for _ in dates]
        a_vals = [v for d in sample_dates for v in by_date_a[d]]
        b_vals = [v for d in sample_dates for v in by_date_b[d]]
        diffs.append(sum(b_vals) / len(b_vals) - sum(a_vals) / len(a_vals))
    diffs.sort()
    lo = diffs[int(0.025 * replicates)]
    hi = diffs[min(int(0.975 * replicates), replicates - 1)]
    return {
        "point_diff_log_loss_b_minus_a": point_diff,
        "ci95_descriptive": [lo, hi],
        "replicates": replicates,
        "seed": seed,
        "note": "descriptive and approximate; not a formal hypothesis test",
    }


def build_metrics_report(rows: list[PredictionRow]) -> dict:
    models = list(_MODELS.keys())
    overall_by_model = {m: _aggregate(rows, m) for m in models}
    by_season = {
        season: {m: _aggregate(rows, m, season=season) for m in models}
        for season in EVALUATION_SEASONS
    }
    best_by_log_loss = min(models, key=lambda m: overall_by_model[m]["log_loss"])

    comparisons = {}
    for other in models:
        if other == "expanding_league_prior":
            continue
        comparisons[other] = {
            "overall": _date_block_bootstrap_log_loss_diff(
                rows, "expanding_league_prior", other, season=None
            ),
            "by_season": {
                season: _date_block_bootstrap_log_loss_diff(
                    rows, "expanding_league_prior", other, season=season
                )
                for season in EVALUATION_SEASONS
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
        },
        "models": {
            "overall": overall_by_model,
            "by_season": by_season,
        },
        "comparison": {
            "best_baseline_by_log_loss_overall": best_by_log_loss,
            "log_loss_difference_vs_expanding_league_prior": comparisons,
        },
    }


def write_metrics_report(report: dict, path: Path = DEFAULT_METRICS_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> None:
    rows = run_backtest()
    write_predictions_csv(rows)
    report = build_metrics_report(rows)
    write_metrics_report(report)
    print(f"evaluated {report['total_evaluation_n']} fixtures across {len(_MODELS)} models")
    for model, agg in report["models"]["overall"].items():
        ll, br, rp = agg["log_loss"], agg["brier"], agg["rps"]
        print(f"  {model}: log_loss={ll:.4f} brier={br:.4f} rps={rp:.4f}")
    print(
        f"best by log loss (overall): {report['comparison']['best_baseline_by_log_loss_overall']}"
    )


if __name__ == "__main__":
    main()

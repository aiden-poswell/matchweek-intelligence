"""S04 Stage C: calibration and failure diagnostics, computed entirely from the
verified S04 four-model prediction rows (`data/processed/s04_ablation_predictions_REVIEW.csv`
via `build_attribution_backtest.run_attribution_backtest`) — never hand-entered.

Every figure in `reports/S04_CALIBRATION_AND_FAILURES.md` traces back to
`reports/s04_calibration_diagnostics.json`, which this module writes deterministically.
"""

from __future__ import annotations

import json
from pathlib import Path

from matchweek_intelligence.build_attribution_backtest import (
    AttributionPredictionRow,
    run_attribution_backtest,
)
from matchweek_intelligence.metrics import OUTCOME_ORDER

DEFAULT_OUTPUT_PATH = Path("reports/s04_calibration_diagnostics.json")

_MODEL_NAMES = (
    "expanding_league_prior",
    "rolling_league_frequency",
    "team_goal_poisson",
    "league_only_poisson",
)
_EVALUATION_SEASONS = ("2024-25", "2025-26")
_OUTCOME_TO_PROB_FIELD = {"H": "p_home", "D": "p_draw", "A": "p_away"}
N_BINS = 5


class CalibrationDiagnosticsError(RuntimeError):
    pass


def _fixture_key(r: AttributionPredictionRow) -> tuple:
    return (r.match_date, r.home_team, r.away_team)


def _outcome_calibration(rows: list[AttributionPredictionRow], outcome: str) -> dict:
    field = _OUTCOME_TO_PROB_FIELD[outcome]
    n = len(rows)
    mean_pred = sum(getattr(r, field) for r in rows) / n
    observed = sum(1 for r in rows if r.actual_outcome == outcome) / n
    return {
        "n": n,
        "mean_predicted_pct": mean_pred * 100,
        "observed_pct": observed * 100,
        "gap_pct_points_observed_minus_predicted": (observed - mean_pred) * 100,
    }


def _mean_vs_observed_report(rows: list[AttributionPredictionRow]) -> dict:
    report: dict = {}
    for model in _MODEL_NAMES:
        model_rows = [r for r in rows if r.model_name == model]
        report[model] = {
            "overall": {o: _outcome_calibration(model_rows, o) for o in OUTCOME_ORDER},
            "by_season": {
                season: {
                    o: _outcome_calibration([r for r in model_rows if r.season == season], o)
                    for o in OUTCOME_ORDER
                }
                for season in _EVALUATION_SEASONS
            },
        }
    return report


def _equal_count_bins(rows: list[AttributionPredictionRow], outcome: str) -> list[dict]:
    field = _OUTCOME_TO_PROB_FIELD[outcome]
    ordered = sorted(rows, key=lambda r: (getattr(r, field), _fixture_key(r)))
    n = len(ordered)
    if n < N_BINS:
        return []
    base, remainder = divmod(n, N_BINS)
    bins: list[dict] = []
    start = 0
    for i in range(N_BINS):
        size = base + (1 if i < remainder else 0)
        chunk = ordered[start : start + size]
        start += size
        mean_pred = sum(getattr(r, field) for r in chunk) / len(chunk)
        observed = sum(1 for r in chunk if r.actual_outcome == outcome) / len(chunk)
        bins.append(
            {
                "bin_index": i,
                "n": len(chunk),
                "mean_predicted_pct": mean_pred * 100,
                "observed_rate_pct": observed * 100,
                "predicted_prob_range": [getattr(chunk[0], field), getattr(chunk[-1], field)],
            }
        )
    return bins


def _calibration_bins_report(rows: list[AttributionPredictionRow]) -> dict:
    return {
        model: {
            outcome: _equal_count_bins([r for r in rows if r.model_name == model], outcome)
            for outcome in OUTCOME_ORDER
        }
        for model in _MODEL_NAMES
    }


def _log_loss_by_season(rows: list[AttributionPredictionRow]) -> dict:
    return {
        model: {
            season: {
                "n": len(subset),
                "mean_log_loss": sum(r.log_loss for r in subset) / len(subset),
            }
            for season in _EVALUATION_SEASONS
            for subset in ([r for r in rows if r.model_name == model and r.season == season],)
        }
        for model in _MODEL_NAMES
    }


_PROBABILITY_BAND_EDGES = [0.0, 0.33, 0.45, 0.55, 1.0]
_PROBABILITY_BAND_LABELS = ["<0.33", "0.33-0.45", "0.45-0.55", ">0.55"]


def _favourite_strength_band(r: AttributionPredictionRow) -> str:
    top_p = max(r.p_home, r.p_draw, r.p_away)
    for i in range(len(_PROBABILITY_BAND_LABELS)):
        lo, hi = _PROBABILITY_BAND_EDGES[i], _PROBABILITY_BAND_EDGES[i + 1]
        if lo <= top_p < hi or (i == len(_PROBABILITY_BAND_LABELS) - 1 and top_p == hi):
            return _PROBABILITY_BAND_LABELS[i]
    return _PROBABILITY_BAND_LABELS[-1]


def _log_loss_by_favourite_band(rows: list[AttributionPredictionRow]) -> dict:
    report: dict = {}
    for model in _MODEL_NAMES:
        model_rows = [r for r in rows if r.model_name == model]
        by_band: dict[str, list[AttributionPredictionRow]] = {
            label: [] for label in _PROBABILITY_BAND_LABELS
        }
        for r in model_rows:
            by_band[_favourite_strength_band(r)].append(r)
        report[model] = {
            band: {
                "n": len(subset),
                "mean_log_loss": (sum(r.log_loss for r in subset) / len(subset))
                if subset
                else None,
            }
            for band, subset in by_band.items()
        }
    return report


def _cold_start_subset_report(rows: list[AttributionPredictionRow]) -> dict:
    report: dict = {}
    for model in _MODEL_NAMES:
        model_rows = [r for r in rows if r.model_name == model]
        cold = [r for r in model_rows if r.home_team_cold_start or r.away_team_cold_start]
        warm = [r for r in model_rows if not (r.home_team_cold_start or r.away_team_cold_start)]
        report[model] = {
            "cold_start_n": len(cold),
            "cold_start_mean_log_loss": (sum(r.log_loss for r in cold) / len(cold))
            if cold
            else None,
            "warm_n": len(warm),
            "warm_mean_log_loss": (sum(r.log_loss for r in warm) / len(warm)) if warm else None,
            "note": "descriptive only — N is tiny, no generalisation implied",
        }
    return report


def _worst_scored_fixtures(
    rows: list[AttributionPredictionRow], model: str, top_n: int = 5
) -> list[dict]:
    model_rows = [r for r in rows if r.model_name == model]
    ranked = sorted(model_rows, key=lambda r: (-r.log_loss, _fixture_key(r)))
    return [
        {
            "match_date": r.match_date,
            "season": r.season,
            "home_team": r.home_team,
            "away_team": r.away_team,
            "home_score": r.home_score,
            "away_score": r.away_score,
            "actual_outcome": r.actual_outcome,
            "p_home": r.p_home,
            "p_draw": r.p_draw,
            "p_away": r.p_away,
            "log_loss": r.log_loss,
        }
        for r in ranked[:top_n]
    ]


def _validate_integrity(rows: list[AttributionPredictionRow]) -> None:
    for model in _MODEL_NAMES:
        model_rows = [r for r in rows if r.model_name == model]
        if len(model_rows) != 760:
            raise CalibrationDiagnosticsError(
                f"{model}: expected 760 rows, found {len(model_rows)}"
            )
        keys = {_fixture_key(r) for r in model_rows}
        if len(keys) != 760:
            raise CalibrationDiagnosticsError(f"{model}: fixture keys are not unique")
        for season in _EVALUATION_SEASONS:
            n = sum(1 for r in model_rows if r.season == season)
            if n != 380:
                raise CalibrationDiagnosticsError(f"{model} {season}: expected 380, found {n}")
        for r in model_rows:
            total = r.p_home + r.p_draw + r.p_away
            if not (abs(total - 1.0) <= 1e-9):
                raise CalibrationDiagnosticsError(f"{model}: probabilities sum to {total}, not 1")
            for p in (r.p_home, r.p_draw, r.p_away):
                if not (p > 0):
                    raise CalibrationDiagnosticsError(f"{model}: non-positive probability {p}")
            if r.latest_training_match_date:
                if r.latest_training_match_date >= r.match_date:
                    raise CalibrationDiagnosticsError(
                        f"{model}: training cutoff {r.latest_training_match_date} "
                        f"does not strictly precede fixture {r.match_date}"
                    )
        if any(r.season == "2026-27" for r in model_rows):
            raise CalibrationDiagnosticsError(f"{model}: 2026/27 present")


def build_report(rows: list[AttributionPredictionRow] | None = None) -> dict:
    rows = rows if rows is not None else run_attribution_backtest()
    _validate_integrity(rows)

    return {
        "n_total_rows": len(rows),
        "n_models": len(_MODEL_NAMES),
        "models": list(_MODEL_NAMES),
        "evaluation_seasons": list(_EVALUATION_SEASONS),
        "mean_vs_observed": _mean_vs_observed_report(rows),
        "equal_count_bins": _calibration_bins_report(rows),
        "log_loss_by_season": _log_loss_by_season(rows),
        "log_loss_by_favourite_band": _log_loss_by_favourite_band(rows),
        "cold_start_subset": _cold_start_subset_report(rows),
        "worst_scored_fixtures": {
            model: _worst_scored_fixtures(rows, model) for model in _MODEL_NAMES
        },
    }


def write_report(report: dict, path: Path = DEFAULT_OUTPUT_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> None:
    report = build_report()
    write_report(report)
    draw_gap = report["mean_vs_observed"]["team_goal_poisson"]["overall"]["D"][
        "gap_pct_points_observed_minus_predicted"
    ]
    print(f"team_goal_poisson overall draw gap: {draw_gap:+.4f}pp")
    print(f"wrote {DEFAULT_OUTPUT_PATH}")


if __name__ == "__main__":
    main()

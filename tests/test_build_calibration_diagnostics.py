"""Calibration diagnostics tests: integrity gate, deterministic equal-count binning,
and exact reproduction of the independently-verified S03 draw-calibration anchors."""

from __future__ import annotations

import pytest

from matchweek_intelligence.build_attribution_backtest import (
    AttributionPredictionRow,
    run_attribution_backtest,
)
from matchweek_intelligence.build_calibration_diagnostics import (
    N_BINS,
    CalibrationDiagnosticsError,
    _equal_count_bins,
    build_report,
)
from matchweek_intelligence.fetch import DEFAULT_MANIFEST_PATH, DEFAULT_RAW_DIR
from matchweek_intelligence.model_inputs import load_eligible_historical_records

_REAL_CACHE_AVAILABLE = DEFAULT_MANIFEST_PATH.exists() and (DEFAULT_RAW_DIR / "2024-25").exists()
requires_real_cache = pytest.mark.skipif(
    not _REAL_CACHE_AVAILABLE, reason="real pinned-commit cache not present — skipping honestly"
)


def _row(**overrides) -> AttributionPredictionRow:
    base = dict(
        match_date="2024-08-16",
        season="2024-25",
        home_team="A",
        away_team="B",
        home_score=1,
        away_score=0,
        actual_outcome="H",
        model_name="team_goal_poisson",
        p_home=0.5,
        p_draw=0.3,
        p_away=0.2,
        training_n=380,
        latest_training_match_date="2024-05-19",
        home_team_exposure=19,
        away_team_exposure=19,
        home_team_cold_start=False,
        away_team_cold_start=False,
        log_loss=0.1,
        brier=0.1,
        rps=0.1,
        accuracy_hit=True,
        lambda_home="1.5",
        lambda_away="1.2",
        included_mass="0.999999",
        tail_mass="1e-12",
        max_goals="20",
    )
    base.update(overrides)
    return AttributionPredictionRow(**base)


@requires_real_cache
def test_real_draw_calibration_matches_the_independently_verified_s03_anchors():
    rows = run_attribution_backtest(all_records=load_eligible_historical_records())
    report = build_report(rows=rows)
    overall = report["mean_vs_observed"]["team_goal_poisson"]["overall"]["D"]
    assert overall["mean_predicted_pct"] == pytest.approx(22.3843, abs=1e-3)
    assert overall["observed_pct"] == pytest.approx(25.9211, abs=1e-3)
    assert overall["gap_pct_points_observed_minus_predicted"] == pytest.approx(3.5368, abs=1e-3)

    by_season = report["mean_vs_observed"]["team_goal_poisson"]["by_season"]
    assert by_season["2024-25"]["D"]["mean_predicted_pct"] == pytest.approx(21.89, abs=0.01)
    assert by_season["2024-25"]["D"]["observed_pct"] == pytest.approx(24.47, abs=0.01)
    assert by_season["2025-26"]["D"]["mean_predicted_pct"] == pytest.approx(22.88, abs=0.01)
    assert by_season["2025-26"]["D"]["observed_pct"] == pytest.approx(27.37, abs=0.01)


@requires_real_cache
def test_build_report_fails_closed_before_writing_if_integrity_is_violated(monkeypatch):
    rows = run_attribution_backtest(all_records=load_eligible_historical_records())
    tampered = list(rows)
    # Corrupt one row's probabilities to no longer sum to 1.
    bad = tampered[0]
    tampered[0] = AttributionPredictionRow(**{**bad.__dict__, "p_home": 0.9})
    with pytest.raises(CalibrationDiagnosticsError, match="sum to"):
        build_report(rows=tampered)


def test_equal_count_bins_are_deterministic_under_tie_break():
    # Five fixtures all sharing the exact same predicted probability for H — the
    # deterministic fixture-key tie-break must still produce a stable, reproducible
    # ordering (and hence stable bin membership) across repeated calls.
    rows = [
        _row(home_team=f"Team{i:02d}", away_team="Z", p_home=0.5, p_draw=0.25, p_away=0.25)
        for i in range(10)
    ]
    bins_a = _equal_count_bins(rows, "H")
    bins_b = _equal_count_bins(rows, "H")
    assert bins_a == bins_b
    assert len(bins_a) == N_BINS
    assert sum(b["n"] for b in bins_a) == len(rows)


def test_equal_count_bins_respects_at_most_five_bins_and_reports_n():
    rows = [
        _row(home_team=f"Team{i:02d}", p_home=0.1 + 0.08 * i, p_draw=0.3, p_away=0.6 - 0.08 * i)
        for i in range(10)
    ]
    bins = _equal_count_bins(rows, "H")
    assert len(bins) <= N_BINS
    for b in bins:
        assert b["n"] > 0
        assert "mean_predicted_pct" in b
        assert "observed_rate_pct" in b


def test_equal_count_bins_empty_when_fewer_rows_than_bins():
    rows = [_row(home_team="OnlyOne")]
    assert _equal_count_bins(rows, "H") == []

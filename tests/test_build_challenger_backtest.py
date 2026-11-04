"""S05 challenger backtest orchestration tests: row/grain integrity, old-model
preservation against the frozen S04 CSV, zero 2026/27, and fail-closed validation."""

from __future__ import annotations

from datetime import date

import pytest

from matchweek_intelligence.build_attribution_backtest import run_attribution_backtest
from matchweek_intelligence.build_challenger_backtest import (
    ALL_MODEL_NAMES,
    ChallengerBacktestError,
    ChallengerPredictionRow,
    build_metrics_report,
    run_challenger_backtest,
)
from matchweek_intelligence.fetch import DEFAULT_MANIFEST_PATH, DEFAULT_RAW_DIR
from matchweek_intelligence.model_inputs import ModelRecord, load_eligible_historical_records
from matchweek_intelligence.prediction_row_validation import PredictionRowValidationError

_REAL_CACHE_AVAILABLE = DEFAULT_MANIFEST_PATH.exists() and (DEFAULT_RAW_DIR / "2024-25").exists()
requires_real_cache = pytest.mark.skipif(
    not _REAL_CACHE_AVAILABLE, reason="real pinned-commit cache not present — skipping honestly"
)


@pytest.fixture(scope="module")
def real_records():
    if not _REAL_CACHE_AVAILABLE:
        pytest.skip("real pinned-commit cache not present — skipping honestly")
    return load_eligible_historical_records()


@pytest.fixture(scope="module")
def real_challenger_result(real_records):
    # The full challenger backtest (prequential lambda cache + per-date rho fits) is
    # expensive — computed ONCE per test module and reused read-only by every test
    # below, instead of each test re-running the whole thing from scratch.
    return run_challenger_backtest(all_records=real_records)


@requires_real_cache
def test_real_backtest_produces_exactly_3800_rows_five_models_760_each(real_challenger_result):
    rows, rho_audit = real_challenger_result
    assert len(rows) == 3800
    by_model: dict[str, list] = {}
    for r in rows:
        by_model.setdefault(r.model_name, []).append(r)
    assert set(by_model.keys()) == set(ALL_MODEL_NAMES)
    for model_rows in by_model.values():
        assert len(model_rows) == 760
        keys = {(r.match_date, r.home_team, r.away_team) for r in model_rows}
        assert len(keys) == 760
        n_2425 = sum(1 for r in model_rows if r.season == "2024-25")
        n_2526 = sum(1 for r in model_rows if r.season == "2025-26")
        assert (n_2425, n_2526) == (380, 380)
    assert all(r.season != "2026-27" for r in rows)
    assert len(rho_audit) > 0


@requires_real_cache
def test_old_model_rows_exactly_match_the_frozen_s04_csv_fields(
    real_records, real_challenger_result
):
    s04_rows = run_attribution_backtest(all_records=real_records)
    s04_by_key = {(r.match_date, r.home_team, r.away_team, r.model_name): r for r in s04_rows}
    s05_rows, _ = real_challenger_result
    checked = 0
    for r in s05_rows:
        if r.model_name == "dixon_coles_team_poisson":
            continue
        key = (r.match_date, r.home_team, r.away_team, r.model_name)
        s04_row = s04_by_key[key]
        for field in s04_row.__dataclass_fields__:
            assert getattr(r, field) == getattr(s04_row, field), (
                f"{key} field={field}: s04={getattr(s04_row, field)!r} s05={getattr(r, field)!r}"
            )
        checked += 1
    assert checked == 3040


@requires_real_cache
def test_dixon_coles_rows_have_populated_trace_fields_other_models_leave_blank(
    real_challenger_result,
):
    rows, _ = real_challenger_result
    for r in rows:
        if r.model_name == "dixon_coles_team_poisson":
            assert r.rho != "" and r.rho_fit_status != ""
            assert float(r.rho) == float(r.rho)  # not NaN
        else:
            assert r.rho == "" and r.rho_fit_status == ""


@requires_real_cache
def test_rho_is_identical_for_every_fixture_sharing_the_same_evaluation_date(
    real_challenger_result,
):
    rows, _ = real_challenger_result
    dc_rows = [r for r in rows if r.model_name == "dixon_coles_team_poisson"]
    by_date: dict[str, set[str]] = {}
    for r in dc_rows:
        by_date.setdefault(r.match_date, set()).add(r.rho)
    multi_fixture_dates = {d: rhos for d, rhos in by_date.items() if len(rhos) > 1}
    assert multi_fixture_dates == {}  # every date has exactly one shared rho value


def test_rejects_a_corpus_where_2026_27_is_present():
    records = [
        ModelRecord(
            competition="premier-league",
            season="2026-27",
            match_date=date(2026, 1, 1),
            home_team="A",
            away_team="B",
            home_score=1,
            away_score=0,
            status="played_with_score",
            source_line_no=1,
        )
    ]
    with pytest.raises(ChallengerBacktestError, match="2026/27"):
        run_challenger_backtest(all_records=records)


@requires_real_cache
def test_build_metrics_report_fails_closed_on_a_corrupted_actual_outcome(real_challenger_result):
    rows, rho_audit = real_challenger_result
    mutated = list(rows)
    victim = mutated[0]
    assert victim.home_score > victim.away_score
    mutated[0] = ChallengerPredictionRow(**{**victim.__dict__, "actual_outcome": "A"})
    with pytest.raises(PredictionRowValidationError, match="contradicts"):
        build_metrics_report(mutated, rho_audit)


@requires_real_cache
def test_build_metrics_report_fails_closed_on_a_fabricated_log_loss(real_challenger_result):
    rows, rho_audit = real_challenger_result
    mutated = list(rows)
    mutated[0] = ChallengerPredictionRow(**{**mutated[0].__dict__, "log_loss": 999.0})
    with pytest.raises(PredictionRowValidationError, match="disagrees with"):
        build_metrics_report(mutated, rho_audit)


@requires_real_cache
def test_build_metrics_report_fails_closed_on_cross_model_key_mismatch(real_challenger_result):
    rows, rho_audit = real_challenger_result
    mutated = list(rows)
    victim_idx = next(i for i, r in enumerate(mutated) if r.model_name != mutated[0].model_name)
    mutated[victim_idx] = ChallengerPredictionRow(
        **{**mutated[victim_idx].__dict__, "home_team": "Totally Different FC"}
    )
    with pytest.raises(PredictionRowValidationError, match="key set differs"):
        build_metrics_report(mutated, rho_audit)


@requires_real_cache
def test_build_metrics_report_accepts_the_genuine_s05_rows_unchanged(real_challenger_result):
    rows, rho_audit = real_challenger_result
    report = build_metrics_report(rows, rho_audit)  # must not raise
    assert report["total_evaluation_n"] == 760

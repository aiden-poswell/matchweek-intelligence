"""End-to-end backtest orchestration tests: leakage controls, N/split integrity,
real-cache exact-anchor checks (honestly skipped if the cache is absent), and a tiny
hand-verifiable scoring sample with a deliberately bad model that loses to the prior."""

from __future__ import annotations

from datetime import date

import pytest

from matchweek_intelligence import baseline_models as bm
from matchweek_intelligence import metrics as mx
from matchweek_intelligence.build_baseline_backtest import BaselineBacktestError, run_backtest
from matchweek_intelligence.chronology import completed_training_results_as_of
from matchweek_intelligence.fetch import DEFAULT_MANIFEST_PATH, DEFAULT_RAW_DIR
from matchweek_intelligence.model_inputs import ModelRecord, load_eligible_historical_records

_REAL_CACHE_AVAILABLE = DEFAULT_MANIFEST_PATH.exists() and (DEFAULT_RAW_DIR / "2024-25").exists()
requires_real_cache = pytest.mark.skipif(
    not _REAL_CACHE_AVAILABLE, reason="real pinned-commit cache not present — skipping honestly"
)


def _rec(d: date, home: str, away: str, hs: int, as_: int, season: str = "2023-24") -> ModelRecord:
    return ModelRecord(
        competition="premier-league",
        season=season,
        match_date=d,
        home_team=home,
        away_team=away,
        home_score=hs,
        away_score=as_,
        status="played_with_score",
        source_line_no=1,
    )


# --- 1. First 2024/25 fixture: exact real anchors (honest skip without the real cache) ---


@requires_real_cache
def test_1_first_2024_25_fixture_sees_380_training_matches_and_the_correct_prior():
    all_records = load_eligible_historical_records()
    first_2425 = min(r.match_date for r in all_records if r.season == "2024-25")
    training = completed_training_results_as_of(all_records, first_2425)
    assert len(training) == 380
    h = sum(1 for r in training if r.home_score > r.away_score)
    d = sum(1 for r in training if r.home_score == r.away_score)
    a = sum(1 for r in training if r.home_score < r.away_score)
    assert (h, d, a) == (175, 82, 123)

    fixture = next(r for r in all_records if r.match_date == first_2425)
    pred = bm.expanding_league_prior(training, fixture.home_team, fixture.away_team)
    assert pred.p_home == pytest.approx(176 / 383)
    assert pred.p_draw == pytest.approx(83 / 383)
    assert pred.p_away == pytest.approx(124 / 383)


# --- 2. Prediction-cutoff leakage controls: same-day batch exclusion + positive control ---


def test_2_modifying_same_day_or_future_results_never_changes_the_prediction_for_that_day():
    target_date = date(2024, 1, 10)
    prior_date = date(2024, 1, 5)
    future_date = date(2024, 1, 15)

    base_records = [
        _rec(prior_date, "A", "B", 1, 0),
        _rec(prior_date, "C", "D", 0, 0),
        _rec(target_date, "A", "C", 2, 2),  # the fixture itself, whose result we'll vary
        _rec(target_date, "B", "D", 1, 1),  # another fixture on the same day
        _rec(future_date, "A", "D", 3, 0),  # a future result
    ]
    training_before = completed_training_results_as_of(base_records, target_date)
    pred_before = bm.expanding_league_prior(training_before, "A", "C")

    mutated_records = [
        _rec(prior_date, "A", "B", 1, 0),
        _rec(prior_date, "C", "D", 0, 0),
        _rec(target_date, "A", "C", 0, 5),  # target fixture's OWN result changed
        _rec(target_date, "B", "D", 9, 0),  # another same-day fixture changed
        _rec(future_date, "A", "D", 0, 0),  # future result changed
    ]
    training_after = completed_training_results_as_of(mutated_records, target_date)
    pred_after = bm.expanding_league_prior(training_after, "A", "C")

    assert training_before == training_after
    assert pred_before.as_tuple() == pred_after.as_tuple()


def test_2_positive_control_modifying_a_genuinely_prior_result_does_change_the_prediction():
    target_date = date(2024, 1, 10)
    prior_date = date(2024, 1, 5)

    records_a = [_rec(prior_date, "A", "B", 1, 0)]  # a home win
    records_b = [_rec(prior_date, "A", "B", 0, 0)]  # the SAME fixture, now a draw

    training_a = completed_training_results_as_of(records_a, target_date)
    training_b = completed_training_results_as_of(records_b, target_date)
    pred_a = bm.expanding_league_prior(training_a, "X", "Y")
    pred_b = bm.expanding_league_prior(training_b, "X", "Y")

    assert pred_a.as_tuple() != pred_b.as_tuple()


# --- 5. Real cold-start fixtures resolve to finite, valid, documented predictions ---


@requires_real_cache
def test_5_real_cold_start_fixtures_are_finite_and_present_in_the_backtest():
    rows = run_backtest()
    cold_start_rows = [r for r in rows if r.home_team_cold_start or r.away_team_cold_start]
    assert len(cold_start_rows) > 0  # the real corpus genuinely has promoted-team cases
    for row in cold_start_rows:
        for p in (row.p_home, row.p_draw, row.p_away):
            assert p == p  # not NaN
            assert p not in (float("inf"), float("-inf"))
            assert 0.0 < p < 1.0


# --- 8. Tiny hand-verifiable scoring sample: a deliberately bad model loses to the prior ---


def test_8_a_deliberately_bad_model_scores_worse_than_the_prior_on_a_tiny_known_sample():
    # Two fixtures, both actually home wins. A "confidently wrong" model predicts away
    # win with high confidence; the expanding prior predicts from the (correct-leaning)
    # training history instead. The prior must score better on every proper score.
    training = [_rec(date(2024, 1, 1), "A", "B", 2, 0) for _ in range(9)] + [
        _rec(date(2024, 1, 1), "A", "B", 0, 1)
    ]  # 9 home wins, 1 away win in training history
    prior_pred = bm.expanding_league_prior(training, "X", "Y")

    bad_p_home, bad_p_draw, bad_p_away = 0.05, 0.05, 0.90  # confidently wrong
    actual_outcome = "H"  # the real outcome of the evaluated fixture

    prior_log_loss = mx.log_loss(prior_pred.p_home)
    bad_log_loss = mx.log_loss(bad_p_home)
    assert prior_log_loss < bad_log_loss

    prior_brier = mx.brier_score(*prior_pred.as_tuple(), actual_outcome)
    bad_brier = mx.brier_score(bad_p_home, bad_p_draw, bad_p_away, actual_outcome)
    assert prior_brier < bad_brier

    prior_rps = mx.ranked_probability_score(*prior_pred.as_tuple(), actual_outcome)
    bad_rps = mx.ranked_probability_score(bad_p_home, bad_p_draw, bad_p_away, actual_outcome)
    assert prior_rps < bad_rps


# --- 9. N sums, uniqueness, per-season split; 2026/27 never present -----------------


def test_9_run_backtest_rejects_a_corpus_that_is_not_exactly_760_evaluation_fixtures():
    too_few = [
        _rec(date(2023, 1, 1), "A", "B", 1, 0, season="2023-24"),
        _rec(date(2024, 1, 1), "A", "B", 1, 0, season="2024-25"),
    ]
    with pytest.raises(BaselineBacktestError, match="760"):
        run_backtest(all_records=too_few)


def test_9_run_backtest_rejects_a_corpus_where_2026_27_is_present():
    # Even a structurally-fine-looking corpus must be rejected outright if 2026/27
    # appears anywhere in it — it must never reach prediction or metric computation.
    records = [
        _rec(date(2026, 1, 1), "A", "B", 1, 0, season="2026-27"),
    ]
    with pytest.raises(BaselineBacktestError, match="2026/27"):
        run_backtest(all_records=records)


@requires_real_cache
def test_9_real_backtest_produces_exactly_760_unique_fixtures_380_per_season():
    rows = run_backtest()
    by_model = {}
    for r in rows:
        by_model.setdefault(r.model_name, []).append(r)
    assert set(by_model.keys()) == {
        "expanding_league_prior",
        "rolling_league_frequency",
        "team_goal_poisson",
    }
    for model_rows in by_model.values():
        assert len(model_rows) == 760
        keys = {(r.match_date, r.home_team, r.away_team) for r in model_rows}
        assert len(keys) == 760  # no duplicates
        n_2425 = sum(1 for r in model_rows if r.season == "2024-25")
        n_2526 = sum(1 for r in model_rows if r.season == "2025-26")
        assert (n_2425, n_2526) == (380, 380)
    assert all(r.season != "2026-27" for r in rows)

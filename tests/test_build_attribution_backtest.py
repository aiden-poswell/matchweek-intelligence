"""S04 four-model attribution backtest tests: N/grain integrity, leakage controls on
both Poisson models, and confirmation that S03's original outputs are never touched."""

from __future__ import annotations

from datetime import date

import pytest

from matchweek_intelligence.build_attribution_backtest import (
    AttributionBacktestError,
    AttributionPredictionRow,
    run_attribution_backtest,
)
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


def test_rejects_a_corpus_that_is_not_exactly_760_evaluation_fixtures():
    too_few = [
        _rec(date(2023, 1, 1), "A", "B", 1, 0, season="2023-24"),
        _rec(date(2024, 1, 1), "A", "B", 1, 0, season="2024-25"),
    ]
    with pytest.raises(AttributionBacktestError, match="760"):
        run_attribution_backtest(all_records=too_few)


def test_rejects_a_corpus_where_2026_27_is_present():
    records = [_rec(date(2026, 1, 1), "A", "B", 1, 0, season="2026-27")]
    with pytest.raises(AttributionBacktestError, match="2026/27"):
        run_attribution_backtest(all_records=records)


@requires_real_cache
def test_real_backtest_produces_exactly_3040_rows_four_models_760_each():
    all_records = load_eligible_historical_records()
    rows = run_attribution_backtest(all_records=all_records)
    assert len(rows) == 3040
    by_model: dict[str, list] = {}
    for r in rows:
        by_model.setdefault(r.model_name, []).append(r)
    assert set(by_model.keys()) == {
        "expanding_league_prior",
        "rolling_league_frequency",
        "team_goal_poisson",
        "league_only_poisson",
    }
    for model_rows in by_model.values():
        assert len(model_rows) == 760
        keys = {(r.match_date, r.home_team, r.away_team) for r in model_rows}
        assert len(keys) == 760
        n_2425 = sum(1 for r in model_rows if r.season == "2024-25")
        n_2526 = sum(1 for r in model_rows if r.season == "2025-26")
        assert (n_2425, n_2526) == (380, 380)
    assert all(r.season != "2026-27" for r in rows)


@requires_real_cache
def test_poisson_trace_columns_populated_only_for_poisson_models():
    all_records = load_eligible_historical_records()
    rows = run_attribution_backtest(all_records=all_records)
    for r in rows:
        if r.model_name in ("team_goal_poisson", "league_only_poisson"):
            assert r.lambda_home != ""
            assert r.lambda_away != ""
            assert r.included_mass != ""
            assert r.tail_mass != ""
            assert r.max_goals != ""
            assert float(r.tail_mass) <= 1e-10
            assert float(r.included_mass) >= 1.0 - 1e-10
        else:
            assert r.lambda_home == ""
            assert r.lambda_away == ""
            assert r.included_mass == ""
            assert r.tail_mass == ""
            assert r.max_goals == ""


@requires_real_cache
def test_league_only_poisson_differs_from_team_goal_poisson_on_the_real_corpus():
    # Sanity check that the ablation is actually exercising different machinery on
    # real data, not accidentally collapsing to the same numbers everywhere.
    all_records = load_eligible_historical_records()
    rows = run_attribution_backtest(all_records=all_records)
    team_rows = {
        (r.match_date, r.home_team, r.away_team): r.p_home
        for r in rows
        if r.model_name == "team_goal_poisson"
    }
    league_rows = {
        (r.match_date, r.home_team, r.away_team): r.p_home
        for r in rows
        if r.model_name == "league_only_poisson"
    }
    differing = sum(1 for k in team_rows if abs(team_rows[k] - league_rows[k]) > 1e-9)
    assert differing > 700  # the overwhelming majority of fixtures should differ


def test_leakage_both_poisson_models_unaffected_by_same_day_or_future_mutation():
    from matchweek_intelligence import baseline_models as bm

    target_date = date(2024, 1, 10)
    prior_date = date(2024, 1, 5)
    future_date = date(2024, 1, 15)

    base = [
        _rec(prior_date, "A", "B", 2, 1),
        _rec(prior_date, "C", "D", 1, 1),
        _rec(target_date, "A", "C", 2, 2),
        _rec(future_date, "A", "D", 3, 0),
    ]
    training_before = completed_training_results_as_of(base, target_date)

    mutated = [
        _rec(prior_date, "A", "B", 2, 1),
        _rec(prior_date, "C", "D", 1, 1),
        _rec(target_date, "A", "C", 0, 5),  # same-day mutation
        _rec(future_date, "A", "D", 0, 0),  # future mutation
    ]
    training_after = completed_training_results_as_of(mutated, target_date)

    assert training_before == training_after
    for model_fn in (bm.team_goal_poisson, bm.league_only_poisson):
        pred_before = model_fn(training_before, "A", "C")
        pred_after = model_fn(training_after, "A", "C")
        assert pred_before.as_tuple() == pred_after.as_tuple()


def test_leakage_positive_control_an_earlier_result_changes_both_poisson_predictions():
    from matchweek_intelligence import baseline_models as bm

    prior_date = date(2024, 1, 5)
    training_a = [_rec(prior_date, "A", "B", 3, 1)]
    training_b = [_rec(prior_date, "A", "B", 1, 3)]

    for model_fn in (bm.team_goal_poisson, bm.league_only_poisson):
        pred_a = model_fn(training_a, "A", "B")
        pred_b = model_fn(training_b, "A", "B")
        assert pred_a.as_tuple() != pred_b.as_tuple()


# --- S07 erratum: bootstrap sign-interpretation regression --------------------------
#
# point_diff_log_loss_right_minus_left = mean(right) - mean(left). A previous version
# of the "interpretation" string said "negative means left_model wins", which is
# backwards: a negative value means RIGHT's log loss is lower, i.e. right_model wins.
# This is the same class of bug independently fixed in build_challenger_backtest.py
# for S06 (see tests/test_build_challenger_backtest.py); this module's own sibling
# copy of the bug was deliberately left unfixed in S06 (disclosed in S06 findings)
# because fixing it then would have altered the already-committed, frozen S04
# artifact without a dedicated erratum. S07 is that dedicated erratum.


def _make_exact_loss_row(d: str, model: str, log_loss: float) -> AttributionPredictionRow:
    return AttributionPredictionRow(
        match_date=d,
        season="2024-25",
        home_team="A",
        away_team="B",
        home_score=1,
        away_score=0,
        actual_outcome="H",
        model_name=model,
        p_home=0.5,
        p_draw=0.3,
        p_away=0.2,
        training_n=10,
        latest_training_match_date="",
        home_team_exposure=1,
        away_team_exposure=1,
        home_team_cold_start=False,
        away_team_cold_start=False,
        log_loss=log_loss,
        brier=0.1,
        rps=0.1,
        accuracy_hit=True,
        lambda_home="",
        lambda_away="",
        included_mass="",
        tail_mass="",
        max_goals="",
    )


def test_s07_bootstrap_interpretation_matches_the_actual_sign_direction_both_ways():
    from matchweek_intelligence.build_attribution_backtest import (
        _date_block_bootstrap_log_loss_diff,
    )

    rows = []
    for i in range(60):
        d = f"2024-01-{i + 1:02d}" if i < 31 else f"2024-02-{i - 30:02d}"
        rows.append(_make_exact_loss_row(d, "worse_model", 2.0))
        rows.append(_make_exact_loss_row(d, "better_model", 1.0))

    # Direction 1: right_model (better_model) has the lower log loss -> diff is
    # negative -> the string must say right_model wins.
    result = _date_block_bootstrap_log_loss_diff(
        rows, model_left="worse_model", model_right="better_model", season=None
    )
    assert result["point_diff_log_loss_right_minus_left"] == pytest.approx(-1.0)
    assert "right_model" in result["interpretation"]
    assert "negative means right_model wins" in result["interpretation"]
    assert result["right_model"] == "better_model"

    # Direction 2: swap left/right — right_model (worse_model) now has the HIGHER log
    # loss -> diff is positive -> under the same fixed interpretation string, a
    # positive value correctly implies left_model (better_model) wins instead.
    result_swapped = _date_block_bootstrap_log_loss_diff(
        rows, model_left="better_model", model_right="worse_model", season=None
    )
    assert result_swapped["point_diff_log_loss_right_minus_left"] == pytest.approx(1.0)
    assert result_swapped["left_model"] == "better_model"

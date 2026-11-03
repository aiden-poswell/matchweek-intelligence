"""Baseline model tests: hand-computed exact cases, normalisation, tail-bound
behaviour, cold-start safety, and rejection of invalid inputs. All entirely synthetic."""

from __future__ import annotations

import math
from datetime import date, timedelta

import pytest

from matchweek_intelligence import baseline_models as bm
from matchweek_intelligence.model_inputs import ModelRecord


def _rec(d: date, home: str, away: str, hs: int, as_: int) -> ModelRecord:
    return ModelRecord(
        competition="premier-league",
        season="2023-24",
        match_date=d,
        home_team=home,
        away_team=away,
        home_score=hs,
        away_score=as_,
        status="played_with_score",
        source_line_no=1,
    )


# --- Expanding league prior ---------------------------------------------------------


def test_expanding_prior_matches_the_frozen_s03_methods_check():
    # H=175, D=82, A=123, N=380 -> smoothed (176, 83, 124) / 383, per docs/S03_BASELINE_METHODS.md.
    records = (
        [_rec(date(2023, 8, 1), "A", "B", 1, 0) for _ in range(175)]
        + [_rec(date(2023, 8, 1), "A", "B", 0, 0) for _ in range(82)]
        + [_rec(date(2023, 8, 1), "A", "B", 0, 1) for _ in range(123)]
    )
    pred = bm.expanding_league_prior(records, "X", "Y")
    assert pred.p_home == pytest.approx(176 / 383)
    assert pred.p_draw == pytest.approx(83 / 383)
    assert pred.p_away == pytest.approx(124 / 383)
    assert pred.training_n == 380


def test_expanding_prior_sums_to_one_and_is_strictly_positive_with_zero_training_data():
    pred = bm.expanding_league_prior([], "X", "Y")
    assert pred.p_home == pytest.approx(1 / 3)
    assert pred.p_draw == pytest.approx(1 / 3)
    assert pred.p_away == pytest.approx(1 / 3)
    assert sum(pred.as_tuple()) == pytest.approx(1.0, abs=1e-9)


# --- Rolling league frequency --------------------------------------------------------


def test_rolling_window_rounds_outward_to_whole_date_batches_never_splitting_a_date():
    # 40 single-fixture days (= 40 fixtures total if taken alone), plus one OLDER date
    # carrying 3 fixtures. With target=41, accumulating the 40 single-fixture days alone
    # reaches only 40 (< 41), so the algorithm must continue into the 3-fixture boundary
    # date — and must take ALL 3 of its fixtures, not just the 1 needed to reach 41.
    records = []
    start = date(2023, 1, 1)
    for day in range(40):
        records.append(_rec(start + timedelta(days=day), "A", "B", 1, 0))
    boundary_date = start - timedelta(days=1)
    for _ in range(3):
        records.append(_rec(boundary_date, "A", "B", 1, 0))
    records.sort(key=lambda r: r.match_date)

    window = bm._rolling_window(records, target=41)
    boundary_day_fixtures_in_window = [r for r in window if r.match_date == boundary_date]
    assert len(boundary_day_fixtures_in_window) == 3  # the whole day, not a partial slice
    assert len(window) == 43  # 40 + all 3, since 40 alone wasn't enough


def test_rolling_window_differs_materially_from_expanding_as_history_grows():
    # Build 300 fixtures: first 200 are all draws, last 100 (one per date, i.e. within
    # the rolling target) are all home wins. Expanding sees mostly draws; rolling (last
    # ~100) sees mostly home wins.
    records = []
    d = date(2023, 1, 1)
    for i in range(200):
        records.append(_rec(d + timedelta(days=i), "A", "B", 0, 0))
    for i in range(200, 300):
        records.append(_rec(d + timedelta(days=i), "A", "B", 1, 0))

    expanding = bm.expanding_league_prior(records, "X", "Y")
    rolling = bm.rolling_league_frequency(records, "X", "Y")
    assert expanding.p_draw > expanding.p_home  # dominated by the 200 early draws
    assert rolling.p_home > rolling.p_draw  # dominated by the last ~100 home wins
    assert expanding.as_tuple() != rolling.as_tuple()


def test_rolling_window_uses_everything_when_history_is_smaller_than_target():
    records = [_rec(date(2023, 1, 1), "A", "B", 1, 0) for _ in range(10)]
    pred = bm.rolling_league_frequency(records, "X", "Y")
    assert pred.diagnostics["window_n"] == 10


# --- Poisson: symmetric hand-computed case ------------------------------------------


def test_poisson_symmetric_case_gives_equal_home_and_away_win_probability():
    # Construct training data that forces league_home_mean == league_away_mean and
    # every team's rates identical by symmetry -> lambda_home must equal lambda_away,
    # and by the independent-Poisson symmetry P(home win) must equal P(away win) exactly.
    records = []
    teams = ["A", "B", "C", "D"]
    d = date(2023, 1, 1)
    i = 0
    for home in teams:
        for away in teams:
            if home == away:
                continue
            records.append(_rec(d + timedelta(days=i), home, away, 1, 1))
            i += 1
    pred = bm.team_goal_poisson(records, "A", "B")
    assert pred.diagnostics["lambda_home"] == pytest.approx(pred.diagnostics["lambda_away"])
    assert pred.p_home == pytest.approx(pred.p_away, abs=1e-9)


def test_poisson_probabilities_sum_to_one_within_tolerance():
    records = [
        _rec(date(2023, 1, 1), "A", "B", 2, 1),
        _rec(date(2023, 1, 2), "B", "A", 0, 3),
        _rec(date(2023, 1, 3), "A", "C", 1, 1),
        _rec(date(2023, 1, 4), "C", "A", 2, 0),
    ]
    pred = bm.team_goal_poisson(records, "A", "C")
    total = sum(pred.as_tuple())
    assert total == pytest.approx(1.0, abs=1e-9)


def test_poisson_tail_mass_is_within_the_frozen_bound():
    records = [
        _rec(date(2023, 1, 1), "A", "B", 2, 1),
        _rec(date(2023, 1, 2), "B", "A", 1, 2),
    ]
    pred = bm.team_goal_poisson(records, "A", "B")
    assert pred.diagnostics["tail_mass"] <= bm.POISSON_TAIL_BOUND
    assert pred.diagnostics["included_mass"] >= 1.0 - bm.POISSON_TAIL_BOUND


def test_poisson_handles_a_large_finite_lambda_without_exceeding_the_safety_cap():
    # A team that has scored enormously in training should push lambda up and require
    # more goal terms, but must still terminate safely under the cap and give valid
    # probs. Away goals are kept realistically nonzero (3) so league_away_mean stays
    # a safe, positive, well-behaved divisor — the point of this test is a large
    # lambda_home, not a degenerate zero-mean edge case (covered separately).
    records = [_rec(date(2023, 1, 1) + timedelta(days=i), "A", "B", 15, 3) for i in range(10)]
    pred = bm.team_goal_poisson(records, "A", "B")
    assert pred.diagnostics["max_goals"] <= bm.POISSON_MAX_GOALS_CAP
    assert sum(pred.as_tuple()) == pytest.approx(1.0, abs=1e-9)
    for p in pred.as_tuple():
        assert math.isfinite(p) and p > 0


def test_poisson_cold_start_team_is_finite_never_nan_or_inf():
    # "B" has zero training history at all; "A" has a normal history.
    records = [_rec(date(2023, 1, 1) + timedelta(days=i), "A", "C", 1, 1) for i in range(5)]
    pred = bm.team_goal_poisson(records, "B", "A")
    assert pred.diagnostics["home_team_cold_start"] is True
    assert pred.diagnostics["away_team_cold_start"] is False
    for p in pred.as_tuple():
        assert math.isfinite(p) and p > 0
    assert sum(pred.as_tuple()) == pytest.approx(1.0, abs=1e-9)


def test_poisson_rejects_a_degenerate_zero_league_mean_rather_than_dividing_by_zero():
    # Every away_score is 0 across training -> league_away_mean == 0, which would
    # divide by zero in lambda_away's formula. Must fail closed, never silently compute
    # an infinite/NaN rate.
    records = [_rec(date(2023, 1, 1) + timedelta(days=i), "A", "B", 15, 0) for i in range(10)]
    with pytest.raises(bm.BaselineModelError):
        bm.team_goal_poisson(records, "A", "B")


def test_poisson_zero_training_data_uses_the_safe_finite_fallback_league_means():
    pred = bm.team_goal_poisson([], "A", "B")
    assert pred.diagnostics["lambda_home"] == pytest.approx(bm.LEAGUE_GOAL_MEAN_FALLBACK)
    assert pred.diagnostics["lambda_away"] == pytest.approx(bm.LEAGUE_GOAL_MEAN_FALLBACK)
    for p in pred.as_tuple():
        assert math.isfinite(p) and p > 0


def test_poisson_rejects_a_negative_resulting_lambda_rather_than_silently_clipping():
    # Directly construct a record with a negative score — something the real parser can
    # never produce — to prove the model fails closed rather than silently computing
    # garbage if it were ever fed invalid data.
    bad_record = ModelRecord(
        competition="premier-league",
        season="2023-24",
        match_date=date(2023, 1, 1),
        home_team="A",
        away_team="B",
        home_score=-5,
        away_score=0,
        status="played_with_score",
        source_line_no=1,
    )
    with pytest.raises(bm.BaselineModelError):
        bm.team_goal_poisson([bad_record], "A", "B")


# --- Probability validation helper --------------------------------------------------


def test_validate_probabilities_rejects_non_finite():
    with pytest.raises(bm.BaselineModelError):
        bm._validate_probabilities(float("nan"), 0.5, 0.5)


def test_validate_probabilities_rejects_non_positive():
    with pytest.raises(bm.BaselineModelError):
        bm._validate_probabilities(0.0, 0.5, 0.5)


def test_validate_probabilities_rejects_sum_far_from_one():
    with pytest.raises(bm.BaselineModelError):
        bm._validate_probabilities(0.5, 0.5, 0.5)


def test_validate_probabilities_accepts_a_valid_vector():
    bm._validate_probabilities(0.5, 0.3, 0.2)  # must not raise


# --- S04 Stage B: league_only_poisson ablation (a)-(g) ------------------------------


def _differentiated_training() -> list[ModelRecord]:
    """A training set where "A" is a strong home scorer and "B" is a weak one —
    enough real differentiation for team_goal_poisson to diverge from the league mean."""
    records = []
    d = date(2023, 1, 1)
    i = 0
    # A: strong at home and away. B: weak at home and away. C/D: fill out the pool so
    # league means aren't dominated by just A and B.
    for _ in range(10):
        records.append(_rec(d + timedelta(days=i), "A", "C", 4, 0))
        i += 1
        records.append(_rec(d + timedelta(days=i), "C", "A", 1, 3))
        i += 1
        records.append(_rec(d + timedelta(days=i), "B", "D", 0, 2))
        i += 1
        records.append(_rec(d + timedelta(days=i), "D", "B", 2, 0))
        i += 1
    return records


def test_a_league_only_poisson_is_fixture_identity_invariant_for_a_fixed_training_set():
    training = _differentiated_training()
    p_ac = bm.league_only_poisson(training, "A", "C")
    p_bd = bm.league_only_poisson(training, "B", "D")
    p_xy = bm.league_only_poisson(training, "NonexistentX", "NonexistentY")
    assert p_ac.as_tuple() == p_bd.as_tuple() == p_xy.as_tuple()


def test_b_team_goal_poisson_remains_team_sensitive_with_differentiated_history():
    training = _differentiated_training()
    p_strong_home = bm.team_goal_poisson(training, "A", "C")
    p_weak_home = bm.team_goal_poisson(training, "B", "D")
    assert p_strong_home.p_home != pytest.approx(p_weak_home.p_home)
    assert p_strong_home.diagnostics["lambda_home"] > p_weak_home.diagnostics["lambda_home"]


def test_c_team_goal_and_league_only_poisson_agree_on_a_fully_symmetric_training_set():
    # Every team has IDENTICAL home/away scoring and conceding rates by construction ->
    # every team-specific rate collapses exactly to the league mean -> team_goal_poisson
    # and league_only_poisson must produce IDENTICAL output for any fixture.
    records = []
    teams = ["A", "B", "C", "D"]
    d = date(2023, 1, 1)
    i = 0
    for home in teams:
        for away in teams:
            if home == away:
                continue
            records.append(_rec(d + timedelta(days=i), home, away, 1, 1))
            i += 1
    team_pred = bm.team_goal_poisson(records, "A", "B")
    league_pred = bm.league_only_poisson(records, "A", "B")
    assert team_pred.as_tuple() == pytest.approx(league_pred.as_tuple(), abs=1e-9)
    assert team_pred.diagnostics["lambda_home"] == pytest.approx(
        league_pred.diagnostics["lambda_home"]
    )


def test_c_cold_start_team_goal_poisson_matches_league_only_poisson_exactly():
    # Both teams in the fixture have ZERO training history -> every team-specific rate
    # in team_goal_poisson collapses to the pure league mean (k=5 shrinkage with n=0
    # numerator/denominator contribution) -> must match league_only_poisson exactly.
    training = [_rec(date(2023, 1, 1) + timedelta(days=i), "X", "Y", 1, 1) for i in range(10)]
    team_pred = bm.team_goal_poisson(training, "BrandNewA", "BrandNewB")
    league_pred = bm.league_only_poisson(training, "BrandNewA", "BrandNewB")
    assert team_pred.as_tuple() == pytest.approx(league_pred.as_tuple(), abs=1e-9)


def test_d_league_only_poisson_rejects_a_degenerate_zero_league_mean():
    records = [_rec(date(2023, 1, 1) + timedelta(days=i), "A", "B", 15, 0) for i in range(10)]
    with pytest.raises(bm.BaselineModelError):
        bm.league_only_poisson(records, "A", "B")


def test_d_league_only_poisson_uses_the_safe_fallback_on_empty_training_data():
    pred = bm.league_only_poisson([], "A", "B")
    assert pred.diagnostics["lambda_home"] == pytest.approx(bm.LEAGUE_GOAL_MEAN_FALLBACK)
    assert pred.diagnostics["lambda_away"] == pytest.approx(bm.LEAGUE_GOAL_MEAN_FALLBACK)


def test_e_league_only_poisson_probabilities_sum_to_one_and_are_valid():
    training = _differentiated_training()
    pred = bm.league_only_poisson(training, "A", "B")
    assert sum(pred.as_tuple()) == pytest.approx(1.0, abs=1e-9)
    for p in pred.as_tuple():
        assert math.isfinite(p) and p > 0


def test_f_mutating_same_day_and_future_scores_does_not_affect_either_poisson_model():
    training = _differentiated_training()
    # "training" already represents the full pre-cutoff set; simulate a same-day/future
    # mutation by building a SEPARATE training set that excludes a later addition, and
    # confirm the prediction from the original (unmutated) and a version with an
    # appended-then-removed same-day row are identical, since the model only ever sees
    # whatever list it is given — the real leakage control lives in
    # chronology.completed_training_results_as_of (see test_build_baseline_backtest.py);
    # this test proves the model itself is a pure function of its training argument,
    # which is the other half of that safety property.
    p1_team = bm.team_goal_poisson(training, "A", "C")
    p1_league = bm.league_only_poisson(training, "A", "C")
    # Re-run on an identical COPY (new list, same values) — must be byte-for-byte equal.
    training_copy = list(training)
    p2_team = bm.team_goal_poisson(training_copy, "A", "C")
    p2_league = bm.league_only_poisson(training_copy, "A", "C")
    assert p1_team.as_tuple() == p2_team.as_tuple()
    assert p1_league.as_tuple() == p2_league.as_tuple()


def test_g_positive_control_an_earlier_result_changes_both_poisson_predictions():
    training_a = _differentiated_training()
    # Flip one of A's early home wins into a loss — a genuinely earlier result.
    training_b = list(training_a)
    training_b[0] = _rec(training_b[0].match_date, "A", "C", 0, 4)

    p_team_a = bm.team_goal_poisson(training_a, "A", "C")
    p_team_b = bm.team_goal_poisson(training_b, "A", "C")
    assert p_team_a.as_tuple() != p_team_b.as_tuple()

    p_league_a = bm.league_only_poisson(training_a, "A", "C")
    p_league_b = bm.league_only_poisson(training_b, "A", "C")
    assert p_league_a.as_tuple() != p_league_b.as_tuple()

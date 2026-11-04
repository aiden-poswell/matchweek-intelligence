"""Dixon-Coles unit tests: hand-calculated tau factors, rho=0 equivalence, total
probability, tail mass, sign conventions, bound/optimiser behaviour, and leakage
controls (same-day batching, a postponed/out-of-round fixture, cold-start teams)."""

from __future__ import annotations

import math
from datetime import date, timedelta

import pytest

from matchweek_intelligence import dixon_coles as dc
from matchweek_intelligence.baseline_models import (
    _poisson_outcome_distribution,
    team_goal_poisson_lambdas,
)
from matchweek_intelligence.model_inputs import ModelRecord


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


# --- Hand-calculated tau factors -----------------------------------------------------


def test_tau_00_hand_calculated():
    assert dc.tau(0, 0, lambda_home=1.5, lambda_away=1.2, rho=0.1) == pytest.approx(
        1 - 1.5 * 1.2 * 0.1
    )


def test_tau_10_hand_calculated():
    assert dc.tau(1, 0, lambda_home=1.5, lambda_away=1.2, rho=0.1) == pytest.approx(1 + 1.2 * 0.1)


def test_tau_01_hand_calculated():
    assert dc.tau(0, 1, lambda_home=1.5, lambda_away=1.2, rho=0.1) == pytest.approx(1 + 1.5 * 0.1)


def test_tau_11_hand_calculated():
    assert dc.tau(1, 1, lambda_home=1.5, lambda_away=1.2, rho=0.1) == pytest.approx(1 - 0.1)


def test_tau_is_exactly_one_for_every_other_scoreline():
    for i, j in [(0, 2), (2, 0), (2, 1), (1, 2), (3, 3), (0, 3), (5, 0)]:
        assert dc.tau(i, j, lambda_home=1.5, lambda_away=1.2, rho=0.15) == 1.0


def test_tau_sign_convention_positive_rho_favours_home_and_away_single_goal_wins():
    # Positive rho increases tau(1,0) and tau(0,1) (shifts mass toward 1-0/0-1),
    # while decreasing tau(0,0) and tau(1,1) (away from 0-0/1-1 draws) — the
    # documented Dixon-Coles sign convention, checked directly rather than assumed.
    lh, la, rho = 1.5, 1.2, 0.1
    assert dc.tau(1, 0, lh, la, rho) > 1.0
    assert dc.tau(0, 1, lh, la, rho) > 1.0
    assert dc.tau(0, 0, lh, la, rho) < 1.0
    assert dc.tau(1, 1, lh, la, rho) < 1.0


# --- rho=0 equivalence, total probability, tail mass --------------------------------


def test_rho_zero_recovers_the_frozen_independent_poisson_probabilities_exactly():
    lh, la = 1.8, 1.3
    dc_dist = dc.dixon_coles_outcome_distribution(lh, la, rho=0.0)
    plain_dist = _poisson_outcome_distribution(lh, la)
    assert dc_dist["p_home"] == pytest.approx(plain_dist["p_home"], abs=1e-12)
    assert dc_dist["p_draw"] == pytest.approx(plain_dist["p_draw"], abs=1e-12)
    assert dc_dist["p_away"] == pytest.approx(plain_dist["p_away"], abs=1e-12)


@pytest.mark.parametrize("rho", [-0.15, -0.05, 0.0, 0.05, 0.15])
def test_total_probability_sums_to_one_across_a_range_of_rho(rho):
    dist = dc.dixon_coles_outcome_distribution(1.6, 1.1, rho)
    total = dist["p_home"] + dist["p_draw"] + dist["p_away"]
    assert total == pytest.approx(1.0, abs=1e-9)


def test_tail_mass_diagnostic_is_retained_and_within_the_frozen_bound():
    dist = dc.dixon_coles_outcome_distribution(1.6, 1.1, rho=0.1)
    assert "tail_mass" in dist
    assert dist["tail_mass"] >= 0
    assert dist["included_mass"] > 0.999


def test_extreme_lambda_and_rho_still_produce_finite_valid_probabilities():
    dist = dc.dixon_coles_outcome_distribution(lambda_home=4.0, lambda_away=0.3, rho=-0.19)
    for p in (dist["p_home"], dist["p_draw"], dist["p_away"]):
        assert math.isfinite(p) and p > 0
    assert sum((dist["p_home"], dist["p_draw"], dist["p_away"])) == pytest.approx(1.0, abs=1e-9)


# --- Bounds and the "never clip a negative tau" rule ---------------------------------


def test_bounds_always_contain_zero():
    lo, hi = dc.compute_rho_bounds([(1.8, 1.3), (0.9, 2.5), (3.0, 0.4)])
    assert lo < 0.0 < hi


def test_bounds_are_intersected_across_all_supplied_pairs():
    # A pair with a very large lambda product tightens the upper bound sharply.
    lo_wide, hi_wide = dc.compute_rho_bounds([(1.0, 1.0)])
    lo_tight, hi_tight = dc.compute_rho_bounds([(1.0, 1.0), (5.0, 5.0)])
    assert hi_tight < hi_wide


def test_a_rho_outside_the_valid_range_for_a_pair_raises_rather_than_clips():
    lh, la = 2.0, 2.0  # tau(0,0) = 1 - 4*rho -> invalid for rho >= 0.25
    with pytest.raises(dc.DixonColesError):
        dc.dixon_coles_outcome_distribution(lh, la, rho=0.3)


def test_outer_bound_is_respected():
    lo, hi = dc.compute_rho_bounds([(0.01, 0.01)], outer=dc.RHO_OUTER_BOUND)
    assert lo >= dc.RHO_OUTER_BOUND[0]
    assert hi <= dc.RHO_OUTER_BOUND[1]


# --- Optimiser determinism -----------------------------------------------------------


def test_golden_section_maximizer_is_deterministic_across_repeated_calls():
    def f(x):
        return -((x - 0.05) ** 2)

    r1 = dc._golden_section_maximize(f, -0.2, 0.2)
    r2 = dc._golden_section_maximize(f, -0.2, 0.2)
    assert r1 == r2
    assert r1 == pytest.approx(0.05, abs=1e-6)


def test_golden_section_respects_strict_bounds():
    def f(x):
        return x  # monotonically increasing -> maximum must be pinned at hi

    result = dc._golden_section_maximize(f, -0.2, 0.2)
    assert -0.2 <= result <= 0.2
    assert result == pytest.approx(0.2, abs=1e-6)


# --- fit_rho: insufficient history, boundary disclosure ------------------------------


def test_fit_rho_returns_zero_with_insufficient_history_status_below_the_threshold():
    obs = [(0, 0, 1.0, 1.0)] * (dc.MIN_TRAINING_OBSERVATIONS_FOR_FIT - 1)
    result = dc.fit_rho(obs, [(1.0, 1.0)])
    assert result.rho == 0.0
    assert result.fit_status == "insufficient_history"
    assert result.bound_lo is None and result.bound_hi is None


def test_fit_rho_discloses_a_boundary_fit_rather_than_hiding_it():
    # All observations are pure 0-0 draws with lh=la=1 -> the unconstrained optimum
    # for tau(0,0)=1-rho is rho -> -infinity, so the fit must land exactly at the
    # lower bound and be disclosed as such.
    obs = [(0, 0, 1.0, 1.0)] * dc.MIN_TRAINING_OBSERVATIONS_FOR_FIT
    result = dc.fit_rho(obs, [(1.0, 1.0)])
    assert result.fit_status == "fitted_at_lower_bound"
    assert result.rho == pytest.approx(result.bound_lo, abs=1e-6)


def test_fit_rho_finds_an_interior_optimum_for_a_realistic_mixed_sample():
    lh, la = 1.8, 1.3
    obs = (
        [(0, 0, lh, la)] * 10
        + [(1, 0, lh, la)] * 5
        + [(0, 1, lh, la)] * 5
        + [(1, 1, lh, la)] * 3
        + [(2, 1, lh, la)] * 40
    )
    result = dc.fit_rho(obs, [(lh, la)])
    assert result.fit_status == "fitted_interior"
    assert result.bound_lo < result.rho < result.bound_hi


# --- Leakage controls: same-day batching, postponed fixture, cold-start -------------


def test_same_day_batch_future_mutation_does_not_affect_an_earlier_date_fit():
    from matchweek_intelligence.chronology import completed_training_results_as_of

    target_date = date(2024, 1, 10)
    prior_date = date(2024, 1, 5)
    future_date = date(2024, 1, 15)
    base = [
        _rec(prior_date, "A", "B", 1, 1),
        _rec(prior_date, "C", "D", 2, 1),
        _rec(target_date, "A", "C", 0, 0),
        _rec(target_date, "B", "D", 1, 0),  # same-day sibling
        _rec(future_date, "A", "D", 3, 0),
    ]
    training_before = completed_training_results_as_of(base, target_date)

    mutated = [
        _rec(prior_date, "A", "B", 1, 1),
        _rec(prior_date, "C", "D", 2, 1),
        _rec(target_date, "A", "C", 9, 9),  # target day's own fixture mutated
        _rec(target_date, "B", "D", 0, 9),  # same-day sibling mutated
        _rec(future_date, "A", "D", 0, 0),  # future mutated
    ]
    training_after = completed_training_results_as_of(mutated, target_date)

    assert training_before == training_after


def test_postponed_out_of_round_fixture_is_still_ordered_purely_by_real_match_date():
    # A fixture nominally "Matchday 5" but actually played out of order, after a
    # later-round match, must still be treated strictly by its real match_date for
    # training-set construction — never by any round/matchday label (there is none
    # on ModelRecord at all, by design; this test exists to document the intent).
    from matchweek_intelligence.chronology import completed_training_results_as_of

    early_round_played_late = _rec(date(2024, 2, 1), "A", "B", 1, 1)  # "Matchday 5", rearranged
    later_round_played_earlier = _rec(date(2024, 1, 20), "C", "D", 2, 0)  # "Matchday 10"
    records = [later_round_played_earlier, early_round_played_late]

    training = completed_training_results_as_of(records, date(2024, 2, 1))
    assert training == [later_round_played_earlier]  # ordered by real date, not round number


def test_cold_start_team_uses_the_existing_k5_shrinkage_not_a_new_team_specific_rho():
    # A team with zero training history gets team_goal_poisson's existing k=5
    # shrinkage toward the league mean for its lambda — dixon_coles_team_poisson
    # introduces no second, team-specific parameter of any kind.
    records = [_rec(date(2023, 1, 1) + timedelta(days=i), "X", "Y", 1, 1) for i in range(10)]
    lh, la, home_rates, _ = team_goal_poisson_lambdas(records, "BrandNewTeam", "X")
    assert home_rates.n_home == 0 and home_rates.n_away == 0
    assert math.isfinite(lh) and math.isfinite(la) and lh > 0 and la > 0

    dist = dc.dixon_coles_outcome_distribution(lh, la, rho=-0.05)
    for p in (dist["p_home"], dist["p_draw"], dist["p_away"]):
        assert math.isfinite(p) and p > 0


def test_positive_control_a_genuinely_earlier_result_changes_the_fitted_rho():
    lh, la = 1.8, 1.3
    base_obs = (
        [(0, 0, lh, la)] * 10
        + [(1, 0, lh, la)] * 5
        + [(0, 1, lh, la)] * 5
        + [(1, 1, lh, la)] * 3
        + [(2, 1, lh, la)] * 40
    )
    fit_a = dc.fit_rho(base_obs, [(lh, la)])

    mutated_obs = list(base_obs)
    mutated_obs[0] = (2, 3, lh, la)  # change one genuinely EARLIER observation
    fit_b = dc.fit_rho(mutated_obs, [(lh, la)])

    assert fit_a.rho != fit_b.rho

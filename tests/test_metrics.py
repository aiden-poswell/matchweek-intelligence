"""Proper-scoring-rule tests against hand-computed exact values, per
docs/S03_BASELINE_METHODS.md's frozen conventions."""

import math

import pytest

from matchweek_intelligence.metrics import (
    OUTCOME_ORDER,
    brier_score,
    log_loss,
    ranked_probability_score,
    top_class_accuracy_hit,
)


def test_outcome_order_is_fixed_as_h_d_a():
    assert OUTCOME_ORDER == ("H", "D", "A")


def test_log_loss_of_a_perfect_prediction_is_zero():
    assert log_loss(1.0) == 0.0


def test_log_loss_hand_computed():
    assert log_loss(0.5) == pytest.approx(math.log(2))
    assert log_loss(0.25) == pytest.approx(-math.log(0.25))


def test_log_loss_rejects_non_positive_or_non_finite():
    for bad in (0.0, -0.1, float("nan"), float("inf")):
        with pytest.raises(ValueError):
            log_loss(bad)


def test_brier_perfect_one_hot_prediction_is_zero():
    assert brier_score(1.0, 0.0, 0.0, "H") == pytest.approx(0.0)
    assert brier_score(0.0, 1.0, 0.0, "D") == pytest.approx(0.0)
    assert brier_score(0.0, 0.0, 1.0, "A") == pytest.approx(0.0)


def test_brier_worst_one_hot_prediction_is_two():
    # Predicting (0,0,1) when the outcome is actually H: (0-1)^2 + (0-0)^2 + (1-0)^2 = 2.
    assert brier_score(0.0, 0.0, 1.0, "H") == pytest.approx(2.0)


def test_brier_uniform_prediction_hand_computed():
    # (1/3-1)^2 + (1/3-0)^2 + (1/3-0)^2 = 4/9 + 1/9 + 1/9 = 6/9
    third = 1 / 3
    assert brier_score(third, third, third, "H") == pytest.approx(6 / 9)


def test_brier_rejects_unknown_outcome():
    with pytest.raises(ValueError):
        brier_score(0.5, 0.3, 0.2, "X")


def test_rps_perfect_prediction_at_each_outcome_is_zero():
    assert ranked_probability_score(1.0, 0.0, 0.0, "H") == pytest.approx(0.0)
    assert ranked_probability_score(0.0, 1.0, 0.0, "D") == pytest.approx(0.0)
    assert ranked_probability_score(0.0, 0.0, 1.0, "A") == pytest.approx(0.0)


def test_rps_worst_case_is_one():
    # Predicting (0,0,1) (certain away) when outcome is actually H (the far ordinal end).
    assert ranked_probability_score(0.0, 0.0, 1.0, "H") == pytest.approx(1.0)


def test_rps_uniform_prediction_hand_computed():
    third = 1 / 3
    # c1=1/3, c2=2/3. Outcome H: o1=1, o2=1 -> ((1/3-1)^2+(2/3-1)^2)/2 = (4/9+1/9)/2 = 5/18
    assert ranked_probability_score(third, third, third, "H") == pytest.approx(5 / 18)
    # Outcome D: o1=0, o2=1 -> ((1/3-0)^2+(2/3-1)^2)/2 = (1/9+1/9)/2 = 1/9
    assert ranked_probability_score(third, third, third, "D") == pytest.approx(1 / 9)
    # Outcome A: o1=0, o2=0 -> ((1/3-0)^2+(2/3-0)^2)/2 = (1/9+4/9)/2 = 5/18
    assert ranked_probability_score(third, third, third, "A") == pytest.approx(5 / 18)


def test_rps_is_symmetric_between_the_two_extreme_outcomes_under_uniform_prediction():
    third = 1 / 3
    rps_h = ranked_probability_score(third, third, third, "H")
    rps_a = ranked_probability_score(third, third, third, "A")
    assert rps_h == pytest.approx(rps_a)


def test_rps_rejects_unknown_outcome():
    with pytest.raises(ValueError):
        ranked_probability_score(0.5, 0.3, 0.2, "X")


def test_top_class_accuracy_hit_and_miss():
    assert top_class_accuracy_hit(0.6, 0.2, 0.2, "H") is True
    assert top_class_accuracy_hit(0.6, 0.2, 0.2, "D") is False


def test_top_class_accuracy_tie_break_prefers_h_then_d_then_a():
    assert top_class_accuracy_hit(0.4, 0.4, 0.2, "H") is True
    assert top_class_accuracy_hit(0.4, 0.4, 0.2, "D") is False
    assert top_class_accuracy_hit(0.2, 0.4, 0.4, "D") is True
    assert top_class_accuracy_hit(0.2, 0.4, 0.4, "A") is False


def test_a_non_perfect_model_genuinely_loses_to_a_better_one_on_log_loss():
    # Demonstrates the scoring functions behave sensibly, not that any particular
    # S03 baseline wins — that is an empirical question answered in the backtest.
    good_model_loss = log_loss(0.6)  # correctly leaned toward the true outcome
    bad_model_loss = log_loss(0.2)  # leaned away from the true outcome
    assert good_model_loss < bad_model_loss

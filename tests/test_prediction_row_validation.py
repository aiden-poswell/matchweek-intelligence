"""Stage A: reproduces the independent reviewer's exact S04 integrity counterexamples
using the REAL AttributionPredictionRow and the REAL reporting entrypoints
(`build_attribution_backtest.build_metrics_report`, `build_calibration_diagnostics.build_report`),
proving each one is now rejected. A positive control proves legitimate data still passes."""

from __future__ import annotations

import pytest

from matchweek_intelligence.build_attribution_backtest import (
    AttributionPredictionRow,
    build_metrics_report,
    run_attribution_backtest,
)
from matchweek_intelligence.build_calibration_diagnostics import build_report
from matchweek_intelligence.fetch import DEFAULT_MANIFEST_PATH, DEFAULT_RAW_DIR
from matchweek_intelligence.model_inputs import load_eligible_historical_records
from matchweek_intelligence.prediction_row_validation import (
    PredictionRowValidationError,
    validate_prediction_rows,
)

_REAL_CACHE_AVAILABLE = DEFAULT_MANIFEST_PATH.exists() and (DEFAULT_RAW_DIR / "2024-25").exists()
requires_real_cache = pytest.mark.skipif(
    not _REAL_CACHE_AVAILABLE, reason="real pinned-commit cache not present — skipping honestly"
)


@pytest.fixture(scope="module")
def real_rows() -> list[AttributionPredictionRow]:
    if not _REAL_CACHE_AVAILABLE:
        pytest.skip("real pinned-commit cache not present — skipping honestly")
    return run_attribution_backtest(all_records=load_eligible_historical_records())


def _replace(row: AttributionPredictionRow, **overrides) -> AttributionPredictionRow:
    return AttributionPredictionRow(**{**row.__dict__, **overrides})


# --- Positive control ---------------------------------------------------------------


@requires_real_cache
def test_positive_control_genuine_s04_rows_pass_both_reporting_entrypoints(real_rows):
    build_metrics_report(real_rows)  # must not raise
    build_report(rows=real_rows)  # must not raise


# --- (a) actual_outcome contradicts home_score/away_score ---------------------------


@requires_real_cache
def test_a_actual_outcome_contradicting_scores_is_rejected_by_both_entrypoints(real_rows):
    mutated = list(real_rows)
    victim = mutated[0]
    assert victim.home_score > victim.away_score  # confirm it is really a home win
    mutated[0] = _replace(victim, actual_outcome="A")

    with pytest.raises(PredictionRowValidationError, match="contradicts"):
        build_metrics_report(mutated)
    with pytest.raises(Exception, match="contradicts"):
        build_report(rows=mutated)


# --- (b) outcome/score mismatch for the SAME fixture across different models -------


@requires_real_cache
def test_b_score_mismatch_across_models_for_the_same_fixture_is_rejected(real_rows):
    mutated = list(real_rows)
    victim = mutated[0]
    assert victim.home_score > victim.away_score  # a real home win, confirmed
    # Change this one row's score for ONE model only, keeping it self-consistent (still
    # a home win) so the per-row derived-outcome check alone would NOT catch it — every
    # OTHER model's row for the identical (date, home, away) fixture still carries the
    # real, original score, so only the cross-model agreement check can catch this.
    mutated[0] = _replace(victim, home_score=victim.home_score + 5, actual_outcome="H")
    with pytest.raises(PredictionRowValidationError, match="disagreement across models"):
        build_metrics_report(mutated)


# --- (c) fabricated precomputed log_loss ---------------------------------------------


@requires_real_cache
def test_c_fabricated_log_loss_is_rejected_and_never_contaminates_the_mean(real_rows):
    mutated = list(real_rows)
    mutated[1] = _replace(mutated[1], log_loss=999.0)
    with pytest.raises(PredictionRowValidationError, match="disagrees with"):
        build_metrics_report(mutated)


# --- (d) fixture-key mismatch between models, while all four still have 760 rows ----


@requires_real_cache
def test_d_fixture_key_mismatch_between_models_is_rejected_even_with_correct_row_counts(
    real_rows,
):
    mutated = list(real_rows)
    # Pick one row belonging to a model OTHER than the first row's model, and change
    # its home_team so that model's key set no longer matches the reference set —
    # every model still has exactly 760 rows, only the KEYS now disagree.
    victim_idx = next(i for i, r in enumerate(mutated) if r.model_name != mutated[0].model_name)
    mutated[victim_idx] = _replace(mutated[victim_idx], home_team="Totally Different FC")
    with pytest.raises(PredictionRowValidationError, match="key set differs"):
        build_metrics_report(mutated)


# --- Additional direct validator tests (not routed through either report builder) ---


def _synthetic_valid_rows() -> list[AttributionPredictionRow]:
    base = dict(
        match_date="2024-08-16",
        season="2024-25",
        home_score=2,
        away_score=1,
        actual_outcome="H",
        p_home=0.5,
        p_draw=0.3,
        p_away=0.2,
        training_n=10,
        latest_training_match_date="2024-05-19",
        home_team_exposure=5,
        away_team_exposure=5,
        home_team_cold_start=False,
        away_team_cold_start=False,
        accuracy_hit=True,
        lambda_home="",
        lambda_away="",
        included_mass="",
        tail_mass="",
        max_goals="",
    )
    from matchweek_intelligence import metrics as mx

    ll = mx.log_loss(0.5)
    brier = mx.brier_score(0.5, 0.3, 0.2, "H")
    rps = mx.ranked_probability_score(0.5, 0.3, 0.2, "H")
    rows = []
    for model in ("model_a", "model_b"):
        rows.append(
            AttributionPredictionRow(
                **base,
                home_team="X",
                away_team="Y",
                model_name=model,
                log_loss=ll,
                brier=brier,
                rps=rps,
            )
        )
    return rows


def test_validator_accepts_a_minimal_two_model_synthetic_positive_control():
    rows = _synthetic_valid_rows()
    validate_prediction_rows(
        rows,
        expected_models=frozenset({"model_a", "model_b"}),
        expected_n_per_model=1,
        season_split={"2024-25": 1},
    )  # must not raise


def test_validator_rejects_an_unknown_model_name():
    rows = _synthetic_valid_rows()
    with pytest.raises(PredictionRowValidationError, match="model set mismatch"):
        validate_prediction_rows(
            rows,
            expected_models=frozenset({"model_a", "model_c"}),
            expected_n_per_model=1,
            season_split={"2024-25": 1},
        )


def test_validator_rejects_a_bool_disguised_as_a_score():
    rows = _synthetic_valid_rows()
    rows[0] = _replace(rows[0], home_score=True)
    with pytest.raises(PredictionRowValidationError, match="invalid home_score"):
        validate_prediction_rows(
            rows,
            expected_models=frozenset({"model_a", "model_b"}),
            expected_n_per_model=1,
            season_split={"2024-25": 1},
        )


def test_validator_rejects_a_training_cutoff_on_or_after_the_fixture_date():
    rows = _synthetic_valid_rows()
    rows[0] = _replace(rows[0], latest_training_match_date="2024-08-16")  # == match_date
    with pytest.raises(PredictionRowValidationError, match="does not strictly precede"):
        validate_prediction_rows(
            rows,
            expected_models=frozenset({"model_a", "model_b"}),
            expected_n_per_model=1,
            season_split={"2024-25": 1},
        )


def test_validator_rejects_a_2026_27_row():
    rows = _synthetic_valid_rows()
    rows[0] = _replace(rows[0], season="2026-27")
    with pytest.raises(PredictionRowValidationError, match="2026/27"):
        validate_prediction_rows(
            rows,
            expected_models=frozenset({"model_a", "model_b"}),
            expected_n_per_model=1,
            season_split={"2024-25": 1, "2026-27": 1},
        )


def test_validator_never_writes_anything_itself_and_raises_before_any_aggregation():
    # The validator is a pure check: it has no file I/O of its own, so "no output file
    # is written on failure" reduces to "the caller's write call is never reached" —
    # proven by the report-builder tests above, which raise before any write_* call.
    rows = _synthetic_valid_rows()
    rows[0] = _replace(rows[0], p_home=0.5, p_draw=0.5, p_away=0.5)  # sums to 1.5
    with pytest.raises(PredictionRowValidationError, match="sum to"):
        validate_prediction_rows(
            rows,
            expected_models=frozenset({"model_a", "model_b"}),
            expected_n_per_model=1,
            season_split={"2024-25": 1},
        )

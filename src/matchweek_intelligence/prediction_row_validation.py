"""The shared, strict cross-model prediction-row validator.

An independent reviewer demonstrated a real integrity gap: both
`build_attribution_backtest.build_metrics_report` and
`build_calibration_diagnostics.build_report` trusted the fields on whatever prediction
rows they were handed — including the PRECOMPUTED `log_loss`/`brier`/`rps`/
`accuracy_hit` fields. A row whose `actual_outcome` contradicted its own
`home_score`/`away_score`, or whose `log_loss` was fabricated as `999`, was silently
accepted and contaminated the aggregate mean. The legitimate S04 export itself is
numerically correct (independently re-verified against raw probabilities/outcomes);
the defect was that the REPORTING CONSUMERS never checked.

`validate_prediction_rows` is the single, shared fix. It is parameterised by the
expected model set (NEVER hardcoded to a fixed count — four models for S04, five for
S05's challenger report, and whatever a later slice needs), and it recomputes every
scored field from the raw probabilities and actual outcome using the SAME frozen
`metrics.py` functions — it never trusts a stored score as an input to anything. It
raises `PredictionRowValidationError` with a specific, diagnosable message on the
first violation found; it is not a license to mutate rows into passing, and no caller
may write any output before this validator has returned successfully.
"""

from __future__ import annotations

import math
from collections.abc import Iterable

from matchweek_intelligence import metrics as mx

SCORE_TOLERANCE = 1e-9


class PredictionRowValidationError(RuntimeError):
    """Raised when a set of prediction rows fails the shared integrity checks."""


def _fixture_key(row) -> tuple:
    return (row.match_date, row.home_team, row.away_team)


def _derive_outcome(home_score: int, away_score: int) -> str:
    if home_score > away_score:
        return "H"
    if home_score == away_score:
        return "D"
    return "A"


def validate_prediction_rows(
    rows: Iterable,
    expected_models: frozenset[str],
    expected_n_per_model: int,
    season_split: dict[str, int],
    score_tolerance: float = SCORE_TOLERANCE,
) -> None:
    """Raise `PredictionRowValidationError` on the first violation found; return
    `None` (silently) if every row passes every check. Never mutates its input.
    """
    rows = list(rows)
    if not rows:
        raise PredictionRowValidationError("no prediction rows supplied")

    by_model: dict[str, list] = {}
    for r in rows:
        by_model.setdefault(r.model_name, []).append(r)

    actual_models = frozenset(by_model.keys())
    if actual_models != frozenset(expected_models):
        raise PredictionRowValidationError(
            f"model set mismatch: expected {sorted(expected_models)}, found {sorted(actual_models)}"
        )

    reference_keys: set[tuple] | None = None
    fixture_truth: dict[tuple, tuple[int, int, str]] = {}

    for model in sorted(expected_models):
        model_rows = by_model[model]

        if len(model_rows) != expected_n_per_model:
            raise PredictionRowValidationError(
                f"{model}: expected {expected_n_per_model} rows, found {len(model_rows)}"
            )

        keys = [_fixture_key(r) for r in model_rows]
        key_set = set(keys)
        if len(key_set) != len(keys):
            raise PredictionRowValidationError(f"{model}: duplicate fixture keys present")
        if reference_keys is None:
            reference_keys = key_set
        elif key_set != reference_keys:
            raise PredictionRowValidationError(
                f"{model}: fixture key set differs from the reference model's key set"
            )

        if any(r.season == "2026-27" for r in model_rows):
            raise PredictionRowValidationError(f"{model}: a 2026/27 row is present")

        for season, expected_n in season_split.items():
            n = sum(1 for r in model_rows if r.season == season)
            if n != expected_n:
                raise PredictionRowValidationError(
                    f"{model} season {season}: expected {expected_n} rows, found {n}"
                )

        for r in model_rows:
            key = _fixture_key(r)

            for label, value in (("home_score", r.home_score), ("away_score", r.away_score)):
                if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                    raise PredictionRowValidationError(
                        f"{model} {key}: invalid {label}={value!r} "
                        "(must be a non-negative int, not a bool)"
                    )

            derived = _derive_outcome(r.home_score, r.away_score)
            if r.actual_outcome != derived:
                raise PredictionRowValidationError(
                    f"{model} {key}: actual_outcome={r.actual_outcome!r} contradicts "
                    f"home_score={r.home_score}, away_score={r.away_score} "
                    f"(derived outcome: {derived!r})"
                )

            truth = (r.home_score, r.away_score, r.actual_outcome)
            if key in fixture_truth:
                if fixture_truth[key] != truth:
                    raise PredictionRowValidationError(
                        f"{key}: score/outcome disagreement across models — "
                        f"{fixture_truth[key]} vs {truth} (seen in {model})"
                    )
            else:
                fixture_truth[key] = truth

            probs = (r.p_home, r.p_draw, r.p_away)
            for p in probs:
                if not math.isfinite(p):
                    raise PredictionRowValidationError(
                        f"{model} {key}: non-finite probability {p!r}"
                    )
                if not (p > 0):
                    raise PredictionRowValidationError(
                        f"{model} {key}: non-positive probability {p!r}"
                    )
            total = sum(probs)
            if abs(total - 1.0) > 1e-9:
                raise PredictionRowValidationError(
                    f"{model} {key}: probabilities sum to {total}, not 1 (tol=1e-9)"
                )

            if r.latest_training_match_date and r.latest_training_match_date >= r.match_date:
                raise PredictionRowValidationError(
                    f"{model} {key}: training cutoff {r.latest_training_match_date!r} "
                    f"does not strictly precede fixture date {r.match_date!r}"
                )

            p_map = {"H": r.p_home, "D": r.p_draw, "A": r.p_away}
            try:
                expected_ll = mx.log_loss(p_map[r.actual_outcome])
                expected_brier = mx.brier_score(r.p_home, r.p_draw, r.p_away, r.actual_outcome)
                expected_rps = mx.ranked_probability_score(
                    r.p_home, r.p_draw, r.p_away, r.actual_outcome
                )
                expected_hit = mx.top_class_accuracy_hit(
                    r.p_home, r.p_draw, r.p_away, r.actual_outcome
                )
            except ValueError as exc:
                raise PredictionRowValidationError(f"{model} {key}: {exc}") from exc

            stored_log_loss = float(r.log_loss)
            if (
                not math.isfinite(stored_log_loss)
                or abs(stored_log_loss - expected_ll) > score_tolerance
            ):
                raise PredictionRowValidationError(
                    f"{model} {key}: stored log_loss={r.log_loss!r} disagrees with "
                    f"independently recomputed {expected_ll!r}"
                )
            stored_brier = float(r.brier)
            if (
                not math.isfinite(stored_brier)
                or abs(stored_brier - expected_brier) > score_tolerance
            ):
                raise PredictionRowValidationError(
                    f"{model} {key}: stored brier={r.brier!r} disagrees with "
                    f"independently recomputed {expected_brier!r}"
                )
            stored_rps = float(r.rps)
            if not math.isfinite(stored_rps) or abs(stored_rps - expected_rps) > score_tolerance:
                raise PredictionRowValidationError(
                    f"{model} {key}: stored rps={r.rps!r} disagrees with "
                    f"independently recomputed {expected_rps!r}"
                )
            if bool(r.accuracy_hit) != expected_hit:
                raise PredictionRowValidationError(
                    f"{model} {key}: stored accuracy_hit={r.accuracy_hit!r} disagrees with "
                    f"independently recomputed {expected_hit!r}"
                )

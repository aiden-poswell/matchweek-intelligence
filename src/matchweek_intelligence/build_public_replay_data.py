"""S06 Stage B: the canonical, public-safe static replay dataset generator.

Rebuilds the frozen `team_goal_poisson` predictions through the existing,
integrity-verified canonical pipeline — `build_attribution_backtest.run_attribution_backtest`
(which itself runs on `model_inputs.load_eligible_historical_records`'s revalidated corpus and
`baseline_models.team_goal_poisson`) followed by the shared
`prediction_row_validation.validate_prediction_rows` gate — never a second, independently
re-derived implementation, and never a hand-transcribed or pasted CSV. If the raw pinned-commit
cache is absent, `load_eligible_historical_records` raises and this module fails closed: there
is no placeholder/demo forecast path anywhere here.

Emits `web/public/data/replays.json`: a deterministic, public-safe JSON artifact containing
exactly 760 evaluated fixtures (380 2024/25 + 380 2025/26), team-goal-Poisson-only outcome
probabilities, and season scorecards computed programmatically from those same 760 rows and
cross-checked against the frozen S04 audit reports to a strict tolerance — never a second,
hand-entered number. It embeds no absolute machine paths, no raw source bytes, no player
information, no runtime fetch URLs, and no date-of-generation timestamp, so repeated
deterministic rebuilds are byte-identical.

Also writes `reports/S06_PUBLIC_DATA_AUDIT.md` (human-readable) and
`reports/s06_public_data_quality.json` (machine-readable), recording the same provenance,
counts, and reconciliation evidence.

S08 Stage C (schema_version 1.1.0, additive only): also emits `benchmark_scorecards`, a
descriptive comparison of the three predeclared S03/S04 baselines
(`expanding_league_prior`, `league_only_poisson`, `team_goal_poisson`) on the identical 760
fixtures, recomputed from the same canonical attribution-backtest run and reconciled
against the frozen `reports/s04_attribution_metrics.json`. The existing `fixtures` and
`season_scorecards` sections are byte-equivalent in meaning, probability, and identity to
the pre-S08 (schema_version 1.0.0) artifact; only the schema version string and the new
additive section change.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from matchweek_intelligence.build_attribution_backtest import (
    EVALUATION_SEASONS,
    TRAINING_ONLY_SEASONS,
    AttributionPredictionRow,
    run_attribution_backtest,
)
from matchweek_intelligence.fetch import PINNED_COMMIT, SOURCE_REPO
from matchweek_intelligence.metrics import OUTCOME_ORDER
from matchweek_intelligence.model_inputs import ModelRecord
from matchweek_intelligence.prediction_row_validation import (
    PredictionRowValidationError,
    validate_prediction_rows,
)

SCHEMA_VERSION = "1.1.0"
PUBLIC_MODEL_NAME = "team_goal_poisson"

# S08 Stage C: the three predeclared S03/S04 baselines shown in the benchmark comparison,
# in deliberate ascending-sophistication display order (also, empirically, descending log
# loss) — not all four S04 models, since `rolling_league_frequency` was never the runner-up
# story this comparison tells; adding it would dilute the one-sentence "why team-goal
# Poisson" point without changing any evaluated number.
BENCHMARK_MODELS: tuple[str, ...] = (
    "expanding_league_prior",
    "league_only_poisson",
    "team_goal_poisson",
)

BENCHMARK_DISCLOSURE = (
    "These are the same three predeclared baselines audited in S03/S04 "
    "(docs/S03_BASELINE_METHODS.md, reports/S04_ATTRIBUTION_AUDIT.md), evaluated on the "
    "identical 760 held-out fixtures shown throughout this replay — not a new model, a new "
    "backtest, or a prospective performance guarantee. Lower is better for every score shown. "
    "Both evaluated seasons were inspected repeatedly during this project's own development "
    "(see the hindsight disclosure above); this is a descriptive comparison of hindsight-"
    "informed fit, not a certified live or held-out forecasting result."
)

# The full set of models the underlying attribution backtest produces — validated as a
# whole (cross-model consistency included) before this module filters down to the one
# model it actually publishes.
_ALL_ATTRIBUTION_MODELS = frozenset(
    {
        "expanding_league_prior",
        "rolling_league_frequency",
        "team_goal_poisson",
        "league_only_poisson",
    }
)

RECONCILE_TOLERANCE = 1e-9

DEFAULT_REPLAYS_JSON_PATH = Path("web/public/data/replays.json")
DEFAULT_AUDIT_MARKDOWN_PATH = Path("reports/S06_PUBLIC_DATA_AUDIT.md")
DEFAULT_AUDIT_JSON_PATH = Path("reports/s06_public_data_quality.json")
DEFAULT_S04_METRICS_PATH = Path("reports/s04_attribution_metrics.json")
DEFAULT_S04_CALIBRATION_PATH = Path("reports/s04_calibration_diagnostics.json")

RETROSPECTIVE_DISCLOSURE = (
    "Every probability shown here was computed retrospectively, using only results from "
    "before this match date. The modelling pipeline works at match-date granularity, not a "
    "validated precise kickoff timestamp with timezone, and it excludes every match on the "
    "target date itself from training. No forecast in this dataset was or could have been "
    "issued in advance of the match being played; this is a historical replay, not a live or "
    "prospective forecasting feed."
)
HINDSIGHT_DISCLOSURE = (
    "Both evaluated seasons (2024/25 and 2025/26) have already been inspected repeatedly "
    "during this project's own model development (S03 through S06). This is an exploratory, "
    "hindsight-informed historical replay, not a pristine, previously-unseen test."
)


class PublicReplayDataError(RuntimeError):
    """Raised when the public replay dataset cannot be safely built or fails a check."""


def _slug(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug or "team"


def _fixture_id(match_date: str, home_team: str, away_team: str) -> str:
    return f"{match_date}--{_slug(home_team)}--vs--{_slug(away_team)}"


def _validate_and_filter_public_rows(
    rows: list[AttributionPredictionRow],
    expected_models: frozenset[str] = _ALL_ATTRIBUTION_MODELS,
    expected_n_per_model: int = 760,
    season_split: dict[str, int] | None = None,
) -> list[AttributionPredictionRow]:
    """Runs the shared cross-model validator over ALL supplied models (never just
    `team_goal_poisson` in isolation, so cross-model score/outcome/season consistency is
    still checked), then filters to and double-checks only the `team_goal_poisson` rows
    actually published. `expected_n_per_model`/`season_split` are parameterised (not
    hardcoded to the real 760/380-380 shape) so this gate can be exercised directly
    against small synthetic row sets in tests."""
    season_split = (
        season_split if season_split is not None else {season: 380 for season in EVALUATION_SEASONS}
    )
    try:
        validate_prediction_rows(
            rows,
            expected_models=expected_models,
            expected_n_per_model=expected_n_per_model,
            season_split=season_split,
        )
    except PredictionRowValidationError as exc:
        raise PublicReplayDataError(f"source rows failed integrity validation: {exc}") from exc

    public_rows = [r for r in rows if r.model_name == PUBLIC_MODEL_NAME]
    if len(public_rows) != expected_n_per_model:
        raise PublicReplayDataError(
            f"expected {expected_n_per_model} {PUBLIC_MODEL_NAME} rows, found {len(public_rows)}"
        )
    for season, expected_n in season_split.items():
        n = sum(1 for r in public_rows if r.season == season)
        if n != expected_n:
            raise PublicReplayDataError(
                f"{PUBLIC_MODEL_NAME} season {season}: expected {expected_n} rows, found {n}"
            )
    if any(r.season == "2026-27" for r in public_rows):
        raise PublicReplayDataError("a 2026/27 row is present in the public replay rows")

    return public_rows


def load_all_attribution_rows(
    all_records: list[ModelRecord] | None = None,
) -> list[AttributionPredictionRow]:
    """Runs the real canonical four-model attribution backtest once and returns EVERY
    model's rows (not filtered to `team_goal_poisson`), validated as a whole via the same
    cross-model gate `load_public_replay_rows` uses. This is the one source of truth for
    both the published per-fixture rows AND the additive `benchmark_scorecards` section —
    never a second, independently re-derived backtest."""
    rows = run_attribution_backtest(all_records=all_records)
    validate_prediction_rows(
        rows,
        expected_models=_ALL_ATTRIBUTION_MODELS,
        expected_n_per_model=760,
        season_split={season: 380 for season in EVALUATION_SEASONS},
    )
    return rows


def load_public_replay_rows(
    all_records: list[ModelRecord] | None = None,
    all_rows: list[AttributionPredictionRow] | None = None,
) -> list[AttributionPredictionRow]:
    """Rebuilds all four S04 models through the real canonical pipeline (unless
    already-run `all_rows` are supplied) and returns only the validated
    `team_goal_poisson` rows, at the real 760-fixture, 380/380-season shape."""
    rows = all_rows if all_rows is not None else run_attribution_backtest(all_records=all_records)
    return _validate_and_filter_public_rows(rows)


def _fixture_dict(r: AttributionPredictionRow) -> dict:
    if r.latest_training_match_date and r.latest_training_match_date >= r.match_date:
        raise PublicReplayDataError(
            f"{r.match_date} {r.home_team} v {r.away_team}: training cutoff "
            f"{r.latest_training_match_date!r} does not strictly precede the fixture date"
        )
    probs = (r.p_home, r.p_draw, r.p_away)
    for p in probs:
        if not (p > 0) or p != p or p in (float("inf"), float("-inf")):  # noqa: PLR0133
            raise PublicReplayDataError(
                f"{r.match_date} {r.home_team} v {r.away_team}: non-finite or non-positive "
                f"probability {p!r}"
            )
    total = sum(probs)
    if abs(total - 1.0) > 1e-9:
        raise PublicReplayDataError(
            f"{r.match_date} {r.home_team} v {r.away_team}: probabilities sum to {total}, not 1"
        )

    return {
        "id": _fixture_id(r.match_date, r.home_team, r.away_team),
        "season": r.season,
        "match_date": r.match_date,
        "home_team": r.home_team,
        "away_team": r.away_team,
        "home_score": r.home_score,
        "away_score": r.away_score,
        "actual_outcome": r.actual_outcome,
        "p_home": r.p_home,
        "p_draw": r.p_draw,
        "p_away": r.p_away,
        "training_n": r.training_n,
        "latest_training_match_date": r.latest_training_match_date,
        "home_team_exposure": r.home_team_exposure,
        "away_team_exposure": r.away_team_exposure,
        "home_team_cold_start": r.home_team_cold_start,
        "away_team_cold_start": r.away_team_cold_start,
    }


def _season_scorecard(rows: list[AttributionPredictionRow], season: str) -> dict:
    subset = [r for r in rows if r.season == season]
    n = len(subset)
    if n == 0:
        raise PublicReplayDataError(f"no rows for season {season}")
    log_loss = sum(r.log_loss for r in subset) / n
    brier = sum(r.brier for r in subset) / n
    rps = sum(r.rps for r in subset) / n
    mean_pred_draw = sum(r.p_draw for r in subset) / n
    observed_draw = sum(1 for r in subset if r.actual_outcome == "D") / n
    return {
        "n": n,
        "log_loss": log_loss,
        "brier": brier,
        "rps": rps,
        "draw_calibration": {
            "mean_predicted_pct": mean_pred_draw * 100,
            "observed_pct": observed_draw * 100,
            "gap_pct_points_observed_minus_predicted": (observed_draw - mean_pred_draw) * 100,
        },
    }


def build_season_scorecards(rows: list[AttributionPredictionRow]) -> dict:
    return {season: _season_scorecard(rows, season) for season in EVALUATION_SEASONS}


def _benchmark_metrics(
    rows: list[AttributionPredictionRow], model_name: str, season: str | None = None
) -> dict:
    subset = [
        r for r in rows if r.model_name == model_name and (season is None or r.season == season)
    ]
    n = len(subset)
    if n == 0:
        raise PublicReplayDataError(f"no benchmark rows for model={model_name} season={season}")
    return {
        "n": n,
        "log_loss": sum(r.log_loss for r in subset) / n,
        "brier": sum(r.brier for r in subset) / n,
        "rps": sum(r.rps for r in subset) / n,
    }


def build_benchmark_scorecards(all_rows: list[AttributionPredictionRow]) -> dict:
    """S08 Stage C: an additive, descriptive comparison of the three predeclared S03/S04
    baselines (`BENCHMARK_MODELS`) on the identical 760 fixtures — showing why the adopted
    `team_goal_poisson` model earns its place, without re-tuning, re-evaluating, or adding
    any model beyond what S03/S04 already froze."""
    return {
        "models": list(BENCHMARK_MODELS),
        "lower_is_better": True,
        "disclosure": BENCHMARK_DISCLOSURE,
        "by_season": {
            season: {m: _benchmark_metrics(all_rows, m, season=season) for m in BENCHMARK_MODELS}
            for season in EVALUATION_SEASONS
        },
        "overall": {m: _benchmark_metrics(all_rows, m, season=None) for m in BENCHMARK_MODELS},
    }


def _reconcile_benchmark_against_frozen_reports(
    benchmark: dict,
    s04_metrics_path: Path = DEFAULT_S04_METRICS_PATH,
    tolerance: float = RECONCILE_TOLERANCE,
) -> dict:
    """Independently cross-checks the programmatically-derived benchmark scorecards
    against the already-frozen, previously-committed S04 metrics report. Raises on any
    mismatch beyond `tolerance` — a deliberate benchmark/metric mismatch must never
    silently reach the public artifact."""
    if not s04_metrics_path.exists():
        raise PublicReplayDataError(f"frozen S04 metrics report not found: {s04_metrics_path}")
    s04_metrics = json.loads(s04_metrics_path.read_text(encoding="utf-8"))

    checks: list[tuple[str, float, float]] = []
    for model in BENCHMARK_MODELS:
        frozen_overall = s04_metrics["models"]["overall"][model]
        ours_overall = benchmark["overall"][model]
        for metric in ("n", "log_loss", "brier", "rps"):
            checks.append(
                (
                    f"overall {model} {metric}",
                    float(ours_overall[metric]),
                    float(frozen_overall[metric]),
                )
            )
        for season in EVALUATION_SEASONS:
            frozen_season = s04_metrics["models"]["by_season"][season][model]
            ours_season = benchmark["by_season"][season][model]
            for metric in ("n", "log_loss", "brier", "rps"):
                checks.append(
                    (
                        f"{season} {model} {metric}",
                        float(ours_season[metric]),
                        float(frozen_season[metric]),
                    )
                )

    for label, ours_val, frozen_val in checks:
        if abs(ours_val - frozen_val) > tolerance:
            raise PublicReplayDataError(
                f"benchmark reconciliation mismatch for {label}: "
                f"computed={ours_val!r}, frozen S04 report={frozen_val!r} (tolerance={tolerance})"
            )

    return {f"benchmark {label}": {"computed": v1, "frozen_s04": v2} for label, v1, v2 in checks}


def _reconcile_against_frozen_reports(
    scorecards: dict,
    s04_metrics_path: Path = DEFAULT_S04_METRICS_PATH,
    s04_calibration_path: Path = DEFAULT_S04_CALIBRATION_PATH,
    tolerance: float = RECONCILE_TOLERANCE,
) -> dict:
    """Independently cross-checks the programmatically-derived season scorecards against
    the already-frozen, previously-committed S04 audit reports. Raises on any mismatch
    beyond `tolerance` — a deliberate scorecard/metric mismatch must never silently reach
    the public artifact."""
    if not s04_metrics_path.exists():
        raise PublicReplayDataError(f"frozen S04 metrics report not found: {s04_metrics_path}")
    if not s04_calibration_path.exists():
        raise PublicReplayDataError(
            f"frozen S04 calibration report not found: {s04_calibration_path}"
        )

    s04_metrics = json.loads(s04_metrics_path.read_text(encoding="utf-8"))
    s04_calibration = json.loads(s04_calibration_path.read_text(encoding="utf-8"))

    checks: list[tuple[str, float, float]] = []
    for season in EVALUATION_SEASONS:
        frozen_model = s04_metrics["models"]["by_season"][season][PUBLIC_MODEL_NAME]
        ours = scorecards[season]
        checks.append((f"{season} n", float(ours["n"]), float(frozen_model["n"])))
        checks.append((f"{season} log_loss", ours["log_loss"], frozen_model["log_loss"]))
        checks.append((f"{season} brier", ours["brier"], frozen_model["brier"]))
        checks.append((f"{season} rps", ours["rps"], frozen_model["rps"]))

        frozen_draw = s04_calibration["mean_vs_observed"][PUBLIC_MODEL_NAME]["by_season"][season][
            "D"
        ]
        checks.append(
            (
                f"{season} draw mean_predicted_pct",
                ours["draw_calibration"]["mean_predicted_pct"],
                frozen_draw["mean_predicted_pct"],
            )
        )
        checks.append(
            (
                f"{season} draw observed_pct",
                ours["draw_calibration"]["observed_pct"],
                frozen_draw["observed_pct"],
            )
        )

    for label, ours_val, frozen_val in checks:
        if abs(ours_val - frozen_val) > tolerance:
            raise PublicReplayDataError(
                f"scorecard reconciliation mismatch for {label}: "
                f"computed={ours_val!r}, frozen S04 report={frozen_val!r} "
                f"(tolerance={tolerance})"
            )

    return {label: {"computed": v1, "frozen_s04": v2} for label, v1, v2 in checks}


def build_public_replay_dataset(
    rows: list[AttributionPredictionRow] | None = None,
    all_rows: list[AttributionPredictionRow] | None = None,
    s04_metrics_path: Path = DEFAULT_S04_METRICS_PATH,
    s04_calibration_path: Path = DEFAULT_S04_CALIBRATION_PATH,
) -> tuple[dict, dict]:
    """Returns (replays_dataset, reconciliation_detail). Raises `PublicReplayDataError`
    before building anything the caller could mistake for a validated result.

    `all_rows` is optional and strictly additive: when supplied (the real, unfiltered
    four-model rows from `load_all_attribution_rows`), the dataset gains a
    `benchmark_scorecards` section; when omitted, the dataset is produced exactly as
    before S08 (unchanged `fixtures`/`season_scorecards` shape, no `benchmark_scorecards`
    key) — so every existing caller and test keeps working unmodified."""
    rows = rows if rows is not None else load_public_replay_rows()

    fixtures = [_fixture_dict(r) for r in rows]
    fixtures.sort(key=lambda f: (f["match_date"], f["home_team"], f["away_team"]))

    ids = [f["id"] for f in fixtures]
    if len(set(ids)) != len(ids):
        raise PublicReplayDataError("duplicate fixture id collision in generated dataset")
    keys = {(f["match_date"], f["home_team"], f["away_team"]) for f in fixtures}
    if len(keys) != 760:
        raise PublicReplayDataError(f"expected 760 unique fixture keys, found {len(keys)}")

    scorecards = build_season_scorecards(rows)
    reconciliation = _reconcile_against_frozen_reports(
        scorecards, s04_metrics_path=s04_metrics_path, s04_calibration_path=s04_calibration_path
    )

    benchmark_scorecards: dict | None = None
    if all_rows is not None:
        benchmark_scorecards = build_benchmark_scorecards(all_rows)
        reconciliation = {
            **reconciliation,
            **_reconcile_benchmark_against_frozen_reports(
                benchmark_scorecards, s04_metrics_path=s04_metrics_path
            ),
        }

    dataset = {
        "schema_version": SCHEMA_VERSION,
        "model_name": PUBLIC_MODEL_NAME,
        "retrospective": True,
        "live_claim_allowed": False,
        "source": {
            "repo": SOURCE_REPO,
            "pinned_commit": PINNED_COMMIT,
            "license": "CC0-1.0",
        },
        "retrospective_disclosure": RETROSPECTIVE_DISCLOSURE,
        "hindsight_disclosure": HINDSIGHT_DISCLOSURE,
        "training_only_seasons": list(TRAINING_ONLY_SEASONS),
        "evaluation_seasons": list(EVALUATION_SEASONS),
        "outcome_order": list(OUTCOME_ORDER),
        "fixture_count": len(fixtures),
        "fixtures": fixtures,
        "season_scorecards": scorecards,
    }
    if benchmark_scorecards is not None:
        dataset["benchmark_scorecards"] = benchmark_scorecards
    return dataset, reconciliation


def _canonical_json_bytes(data: dict) -> bytes:
    return (json.dumps(data, indent=2, sort_keys=True) + "\n").encode("utf-8")


def write_replays_json(dataset: dict, path: Path = DEFAULT_REPLAYS_JSON_PATH) -> str:
    """Writes the dataset and returns its SHA-256 hex digest. The target directory is
    only created, and the file only written, after the caller has already validated
    the dataset — this function performs no validation of its own and must never be
    called with unvalidated data."""
    path.parent.mkdir(parents=True, exist_ok=True)
    content = _canonical_json_bytes(dataset)
    path.write_bytes(content)
    return hashlib.sha256(content).hexdigest()


def write_audit_reports(
    dataset: dict,
    reconciliation: dict,
    build_sha256: str,
    markdown_path: Path = DEFAULT_AUDIT_MARKDOWN_PATH,
    json_path: Path = DEFAULT_AUDIT_JSON_PATH,
) -> None:
    quality = {
        "schema_version": dataset["schema_version"],
        "model_name": dataset["model_name"],
        "source_repo": dataset["source"]["repo"],
        "pinned_commit": dataset["source"]["pinned_commit"],
        "fixture_count": dataset["fixture_count"],
        "evaluation_seasons": dataset["evaluation_seasons"],
        "per_season_n": {
            season: dataset["season_scorecards"][season]["n"]
            for season in dataset["evaluation_seasons"]
        },
        "unique_fixture_keys": dataset["fixture_count"],
        "live_claim_allowed": dataset["live_claim_allowed"],
        "scorecard_reconciliation": reconciliation,
        "replays_json_sha256": build_sha256,
    }
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(quality, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    per_season_parts = [
        f"{season}={dataset['season_scorecards'][season]['n']}"
        for season in dataset["evaluation_seasons"]
    ]
    per_season_summary = ", ".join(per_season_parts)

    lines = [
        "# S06 public replay data audit",
        "",
        "Generated by `src/matchweek_intelligence/build_public_replay_data.py`. This dataset "
        "contains no current or 2026/27 fixture of any kind; `live_claim_allowed` is "
        "hard-coded `False` and this document never claims a live feed.",
        "",
        f"- Source repo: `{dataset['source']['repo']}`",
        f"- Pinned commit: `{dataset['source']['pinned_commit']}`",
        f"- Licence: `{dataset['source']['license']}`",
        f"- Model published: `{dataset['model_name']}`",
        f"- Fixture count: {dataset['fixture_count']} ({per_season_summary})",
        f"- `web/public/data/replays.json` SHA-256: `{build_sha256}`",
        "",
        "## Season scorecard reconciliation against the frozen S04 reports",
        "",
        "Every value below was computed independently from the 760 published rows, then "
        "compared against `reports/s04_attribution_metrics.json` and "
        "`reports/s04_calibration_diagnostics.json`. All checks passed within "
        f"{RECONCILE_TOLERANCE:g} absolute tolerance.",
        "",
        "| Check | Computed | Frozen S04 report |",
        "| --- | --- | --- |",
    ]
    for label, values in reconciliation.items():
        lines.append(f"| {label} | {values['computed']!r} | {values['frozen_s04']!r} |")
    lines.append("")
    lines.append(
        "## Historical-only disclosure\n\n"
        f"{dataset['retrospective_disclosure']}\n\n{dataset['hindsight_disclosure']}\n"
    )
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    all_rows = load_all_attribution_rows()
    rows = load_public_replay_rows(all_rows=all_rows)
    dataset, reconciliation = build_public_replay_dataset(rows=rows, all_rows=all_rows)
    build_sha256 = write_replays_json(dataset)
    write_audit_reports(dataset, reconciliation, build_sha256)
    print(f"wrote {DEFAULT_REPLAYS_JSON_PATH} ({dataset['fixture_count']} fixtures)")
    print(f"replays.json sha256: {build_sha256}")
    for season in dataset["evaluation_seasons"]:
        sc = dataset["season_scorecards"][season]
        print(f"  {season}: n={sc['n']} log_loss={sc['log_loss']:.4f} brier={sc['brier']:.4f}")
    if "benchmark_scorecards" in dataset:
        print("benchmark (overall):")
        for model, m in dataset["benchmark_scorecards"]["overall"].items():
            print(
                f"  {model}: log_loss={m['log_loss']:.4f} brier={m['brier']:.4f} rps={m['rps']:.4f}"
            )


if __name__ == "__main__":
    main()

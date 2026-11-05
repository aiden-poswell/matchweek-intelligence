"""S06 Stage B: tests for the canonical public replay dataset generator.

Synthetic tests exercise every fail-closed check without needing the real pinned-commit
cache; a small set of `requires_real_cache` tests prove the real 760-fixture pipeline
actually reconciles against the frozen S04 reports and rebuilds deterministically."""

from __future__ import annotations

import json

import pytest

from matchweek_intelligence.build_attribution_backtest import AttributionPredictionRow
from matchweek_intelligence.build_public_replay_data import (
    PublicReplayDataError,
    _fixture_dict,
    _reconcile_against_frozen_reports,
    _validate_and_filter_public_rows,
    build_public_replay_dataset,
    build_season_scorecards,
    load_public_replay_rows,
    write_audit_reports,
    write_replays_json,
)
from matchweek_intelligence.fetch import DEFAULT_MANIFEST_PATH, DEFAULT_RAW_DIR
from matchweek_intelligence.model_inputs import ModelInputError, load_eligible_historical_records

_REAL_CACHE_AVAILABLE = DEFAULT_MANIFEST_PATH.exists() and (DEFAULT_RAW_DIR / "2024-25").exists()
requires_real_cache = pytest.mark.skipif(
    not _REAL_CACHE_AVAILABLE, reason="real pinned-commit cache not present — skipping honestly"
)

_ALL_FOUR_MODELS = frozenset(
    {
        "expanding_league_prior",
        "rolling_league_frequency",
        "team_goal_poisson",
        "league_only_poisson",
    }
)


def _row(
    *,
    match_date: str = "2024-08-16",
    season: str = "2024-25",
    home_team: str = "Alpha FC",
    away_team: str = "Beta FC",
    model_name: str = "team_goal_poisson",
    home_score: int = 2,
    away_score: int = 1,
    actual_outcome: str = "H",
    p_home: float = 0.5,
    p_draw: float = 0.3,
    p_away: float = 0.2,
    latest_training_match_date: str = "2024-05-19",
    training_n: int = 10,
) -> AttributionPredictionRow:
    from matchweek_intelligence import metrics as mx

    return AttributionPredictionRow(
        match_date=match_date,
        season=season,
        home_team=home_team,
        away_team=away_team,
        home_score=home_score,
        away_score=away_score,
        actual_outcome=actual_outcome,
        model_name=model_name,
        p_home=p_home,
        p_draw=p_draw,
        p_away=p_away,
        training_n=training_n,
        latest_training_match_date=latest_training_match_date,
        home_team_exposure=5,
        away_team_exposure=5,
        home_team_cold_start=False,
        away_team_cold_start=False,
        log_loss=mx.log_loss(
            p_home if actual_outcome == "H" else (p_draw if actual_outcome == "D" else p_away)
        ),
        brier=mx.brier_score(p_home, p_draw, p_away, actual_outcome),
        rps=mx.ranked_probability_score(p_home, p_draw, p_away, actual_outcome),
        accuracy_hit=mx.top_class_accuracy_hit(p_home, p_draw, p_away, actual_outcome),
        lambda_home="",
        lambda_away="",
        included_mass="",
        tail_mass="",
        max_goals="",
    )


def _two_fixture_four_model_rows(
    *, season_a: str = "2024-25", season_b: str = "2025-26"
) -> list[AttributionPredictionRow]:
    """A minimal, internally-consistent two-fixture x four-model synthetic corpus — the
    smallest shape that can exercise `_validate_and_filter_public_rows` end to end."""
    fixtures = [
        ("2024-08-16", season_a, "Alpha FC", "Beta FC", 2, 1, "H"),
        ("2025-08-16", season_b, "Gamma FC", "Delta FC", 0, 0, "D"),
    ]
    rows = []
    for model in _ALL_FOUR_MODELS:
        for match_date, season, home, away, hs, as_, outcome in fixtures:
            rows.append(
                _row(
                    match_date=match_date,
                    season=season,
                    home_team=home,
                    away_team=away,
                    model_name=model,
                    home_score=hs,
                    away_score=as_,
                    actual_outcome=outcome,
                    p_home=0.5 if outcome != "D" else 0.3,
                    p_draw=0.3,
                    p_away=0.2 if outcome != "D" else 0.4,
                )
            )
    return rows


_SMALL_SEASON_SPLIT = {"2024-25": 1, "2025-26": 1}


# --- Fail-closed checks on the shared cross-model gate, via small synthetic corpora ----


def test_positive_control_a_consistent_small_synthetic_corpus_passes():
    rows = _two_fixture_four_model_rows()
    public_rows = _validate_and_filter_public_rows(
        rows, expected_n_per_model=2, season_split=_SMALL_SEASON_SPLIT
    )
    assert len(public_rows) == 2
    assert all(r.model_name == "team_goal_poisson" for r in public_rows)


def test_wrong_model_label_is_rejected():
    rows = _two_fixture_four_model_rows()
    mutated = [
        r
        if r.model_name != "league_only_poisson"
        else _row(
            model_name="not_a_real_model",
            match_date=r.match_date,
            season=r.season,
            home_team=r.home_team,
            away_team=r.away_team,
        )
        for r in rows
    ]
    with pytest.raises(PublicReplayDataError, match="model set mismatch"):
        _validate_and_filter_public_rows(
            mutated, expected_n_per_model=2, season_split=_SMALL_SEASON_SPLIT
        )


def test_missing_season_is_rejected():
    rows = _two_fixture_four_model_rows(season_a="2024-25", season_b="2024-25")
    with pytest.raises(
        PublicReplayDataError, match="expected 1 rows, found 2|expected 1 rows, found 0"
    ):
        _validate_and_filter_public_rows(
            rows, expected_n_per_model=2, season_split=_SMALL_SEASON_SPLIT
        )


def test_accidental_2026_27_row_is_rejected():
    rows = _two_fixture_four_model_rows(season_b="2026-27")
    with pytest.raises(PublicReplayDataError, match="unsupported season|2026/27"):
        _validate_and_filter_public_rows(
            rows, expected_n_per_model=2, season_split=_SMALL_SEASON_SPLIT
        )


def test_changed_fixture_outcome_across_models_is_rejected():
    rows = _two_fixture_four_model_rows()
    victim_idx = next(i for i, r in enumerate(rows) if r.model_name == "team_goal_poisson")
    victim = rows[victim_idx]
    rows[victim_idx] = _row(
        match_date=victim.match_date,
        season=victim.season,
        home_team=victim.home_team,
        away_team=victim.away_team,
        model_name=victim.model_name,
        home_score=99,
        away_score=0,
        actual_outcome=victim.actual_outcome,  # now contradicts the new score
    )
    with pytest.raises(PublicReplayDataError, match="disagreement across models"):
        _validate_and_filter_public_rows(
            rows, expected_n_per_model=2, season_split=_SMALL_SEASON_SPLIT
        )


def test_duplicated_fixture_is_rejected():
    rows = _two_fixture_four_model_rows()
    # Duplicate one row's fixture key within its own model.
    victim = next(r for r in rows if r.model_name == "team_goal_poisson")
    rows.append(victim)
    with pytest.raises(
        PublicReplayDataError, match="duplicate fixture keys|expected 2 rows, found 3"
    ):
        _validate_and_filter_public_rows(
            rows, expected_n_per_model=2, season_split=_SMALL_SEASON_SPLIT
        )


def test_missing_fixture_is_rejected():
    rows = _two_fixture_four_model_rows()
    rows = [
        r for r in rows if not (r.model_name == "team_goal_poisson" and r.home_team == "Gamma FC")
    ]
    with pytest.raises(PublicReplayDataError, match="expected 2 rows, found 1"):
        _validate_and_filter_public_rows(
            rows, expected_n_per_model=2, season_split=_SMALL_SEASON_SPLIT
        )


def test_past_or_same_day_cutoff_violation_is_rejected():
    rows = _two_fixture_four_model_rows()
    victim_idx = next(i for i, r in enumerate(rows) if r.model_name == "team_goal_poisson")
    victim = rows[victim_idx]
    rows[victim_idx] = _row(
        match_date=victim.match_date,
        season=victim.season,
        home_team=victim.home_team,
        away_team=victim.away_team,
        model_name=victim.model_name,
        latest_training_match_date=victim.match_date,  # == match_date, not strictly before
    )
    with pytest.raises(PublicReplayDataError, match="does not strictly precede"):
        _validate_and_filter_public_rows(
            rows, expected_n_per_model=2, season_split=_SMALL_SEASON_SPLIT
        )


def test_probability_not_summing_to_one_is_rejected_by_the_shared_gate():
    rows = _two_fixture_four_model_rows()
    victim_idx = next(i for i, r in enumerate(rows) if r.model_name == "team_goal_poisson")
    victim = rows[victim_idx]
    rows[victim_idx] = _row(
        match_date=victim.match_date,
        season=victim.season,
        home_team=victim.home_team,
        away_team=victim.away_team,
        model_name=victim.model_name,
        p_home=0.5,
        p_draw=0.5,
        p_away=0.5,  # sums to 1.5
    )
    with pytest.raises(PublicReplayDataError, match="sum to"):
        # log_loss/brier/rps were computed from the ORIGINAL (valid) probabilities inside
        # _row's own helper before mutation would be needed — so this exercises the
        # probability-sum check directly, which fires before any score re-derivation.
        _validate_and_filter_public_rows(
            rows, expected_n_per_model=2, season_split=_SMALL_SEASON_SPLIT
        )


# --- _fixture_dict: the generator's own second gate (bypassing the cross-model check) ---


def test_fixture_dict_rejects_a_same_day_training_cutoff_directly():
    bad = _row(latest_training_match_date="2024-08-16")  # == match_date
    with pytest.raises(PublicReplayDataError, match="does not strictly precede"):
        _fixture_dict(bad)


def test_fixture_dict_rejects_probabilities_not_summing_to_one_directly():
    bad = _row(p_home=0.5, p_draw=0.5, p_away=0.5)
    with pytest.raises(PublicReplayDataError, match="sum to"):
        _fixture_dict(bad)


def test_fixture_dict_accepts_a_genuine_row():
    good = _row()
    d = _fixture_dict(good)
    assert d["id"] == "2024-08-16--alpha-fc--vs--beta-fc"
    assert d["home_team"] == "Alpha FC"
    assert abs((d["p_home"] + d["p_draw"] + d["p_away"]) - 1.0) < 1e-9


# --- Deliberate scorecard-metric mismatch ----------------------------------------------


def test_deliberate_scorecard_mismatch_is_rejected(tmp_path):
    rows = [
        _row(match_date="2024-08-16", season="2024-25", home_team="Alpha FC", away_team="Beta FC"),
        _row(match_date="2025-08-16", season="2025-26", home_team="Gamma FC", away_team="Delta FC"),
    ]
    scorecards = build_season_scorecards(rows)

    fake_s04_metrics = {
        "models": {
            "by_season": {
                "2024-25": {
                    "team_goal_poisson": {
                        "n": 1,
                        "log_loss": 999.0,  # deliberately wrong
                        "brier": scorecards["2024-25"]["brier"],
                        "rps": scorecards["2024-25"]["rps"],
                    }
                },
                "2025-26": {
                    "team_goal_poisson": {
                        "n": 1,
                        "log_loss": scorecards["2025-26"]["log_loss"],
                        "brier": scorecards["2025-26"]["brier"],
                        "rps": scorecards["2025-26"]["rps"],
                    }
                },
            }
        }
    }
    fake_s04_calibration = {
        "mean_vs_observed": {
            "team_goal_poisson": {
                "by_season": {
                    "2024-25": {
                        "D": {
                            "mean_predicted_pct": scorecards["2024-25"]["draw_calibration"][
                                "mean_predicted_pct"
                            ],
                            "observed_pct": scorecards["2024-25"]["draw_calibration"][
                                "observed_pct"
                            ],
                        }
                    },
                    "2025-26": {
                        "D": {
                            "mean_predicted_pct": scorecards["2025-26"]["draw_calibration"][
                                "mean_predicted_pct"
                            ],
                            "observed_pct": scorecards["2025-26"]["draw_calibration"][
                                "observed_pct"
                            ],
                        }
                    },
                }
            }
        }
    }
    metrics_path = tmp_path / "s04_attribution_metrics.json"
    calibration_path = tmp_path / "s04_calibration_diagnostics.json"
    metrics_path.write_text(json.dumps(fake_s04_metrics), encoding="utf-8")
    calibration_path.write_text(json.dumps(fake_s04_calibration), encoding="utf-8")

    with pytest.raises(PublicReplayDataError, match="scorecard reconciliation mismatch"):
        _reconcile_against_frozen_reports(
            scorecards, s04_metrics_path=metrics_path, s04_calibration_path=calibration_path
        )


def test_reconciliation_passes_when_frozen_numbers_genuinely_match(tmp_path):
    rows = [
        _row(match_date="2024-08-16", season="2024-25", home_team="Alpha FC", away_team="Beta FC"),
        _row(match_date="2025-08-16", season="2025-26", home_team="Gamma FC", away_team="Delta FC"),
    ]
    scorecards = build_season_scorecards(rows)

    def _metrics_block(season):
        return {
            "n": 1,
            "log_loss": scorecards[season]["log_loss"],
            "brier": scorecards[season]["brier"],
            "rps": scorecards[season]["rps"],
        }

    def _calibration_block(season):
        return {
            "D": {
                "mean_predicted_pct": scorecards[season]["draw_calibration"]["mean_predicted_pct"],
                "observed_pct": scorecards[season]["draw_calibration"]["observed_pct"],
            }
        }

    fake_s04_metrics = {
        "models": {
            "by_season": {
                "2024-25": {"team_goal_poisson": _metrics_block("2024-25")},
                "2025-26": {"team_goal_poisson": _metrics_block("2025-26")},
            }
        }
    }
    fake_s04_calibration = {
        "mean_vs_observed": {
            "team_goal_poisson": {
                "by_season": {
                    "2024-25": _calibration_block("2024-25"),
                    "2025-26": _calibration_block("2025-26"),
                }
            }
        }
    }
    metrics_path = tmp_path / "s04_attribution_metrics.json"
    calibration_path = tmp_path / "s04_calibration_diagnostics.json"
    metrics_path.write_text(json.dumps(fake_s04_metrics), encoding="utf-8")
    calibration_path.write_text(json.dumps(fake_s04_calibration), encoding="utf-8")

    result = _reconcile_against_frozen_reports(
        scorecards, s04_metrics_path=metrics_path, s04_calibration_path=calibration_path
    )  # must not raise
    assert len(result) == 12  # 2 seasons x 6 checks


# --- Missing/tampered source manifest — the root fail-closed property --------------


def test_missing_source_manifest_fails_closed(tmp_path):
    with pytest.raises(ModelInputError, match="manifest not found"):
        load_eligible_historical_records(manifest_path=tmp_path / "does_not_exist.json")


def test_tampered_manifest_pinned_commit_fails_closed(tmp_path):
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "source_repo": "openfootball/england",
                "pinned_commit": "0" * 40,  # tampered — not the real pinned commit
                "files": [],
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ModelInputError, match="pinned_commit mismatch"):
        load_eligible_historical_records(raw_dir=raw_dir, manifest_path=manifest_path)


# --- Real-cache acceptance tests ------------------------------------------------------


@requires_real_cache
def test_real_pipeline_produces_exactly_760_fixtures_with_reconciling_scorecards():
    public_rows = load_public_replay_rows()
    assert len(public_rows) == 760
    dataset, reconciliation = build_public_replay_dataset(rows=public_rows)
    assert dataset["fixture_count"] == 760
    assert len(dataset["fixtures"]) == 760
    keys = {(f["match_date"], f["home_team"], f["away_team"]) for f in dataset["fixtures"]}
    assert len(keys) == 760
    ids = {f["id"] for f in dataset["fixtures"]}
    assert len(ids) == 760
    for season, expected_n in (("2024-25", 380), ("2025-26", 380)):
        assert dataset["season_scorecards"][season]["n"] == expected_n
    assert len(reconciliation) == 12
    assert dataset["live_claim_allowed"] is False
    assert all(f["season"] != "2026-27" for f in dataset["fixtures"])


@requires_real_cache
def test_real_pipeline_rebuild_is_byte_identical(tmp_path):
    public_rows = load_public_replay_rows()
    dataset_a, recon_a = build_public_replay_dataset(rows=public_rows)
    dataset_b, recon_b = build_public_replay_dataset(rows=public_rows)

    path_a = tmp_path / "a.json"
    path_b = tmp_path / "b.json"
    write_replays_json(dataset_a, path=path_a)
    write_replays_json(dataset_b, path=path_b)
    assert path_a.read_bytes() == path_b.read_bytes()


@requires_real_cache
def test_real_pipeline_first_fixture_sorted_chronologically_is_deterministic():
    public_rows = load_public_replay_rows()
    dataset, _ = build_public_replay_dataset(rows=public_rows)
    first = dataset["fixtures"][0]
    assert first["match_date"] == min(f["match_date"] for f in dataset["fixtures"])


@requires_real_cache
def test_write_audit_reports_runs_without_raising(tmp_path):
    public_rows = load_public_replay_rows()
    dataset, reconciliation = build_public_replay_dataset(rows=public_rows)
    replays_path = tmp_path / "replays.json"
    sha = write_replays_json(dataset, path=replays_path)
    write_audit_reports(
        dataset,
        reconciliation,
        sha,
        markdown_path=tmp_path / "audit.md",
        json_path=tmp_path / "audit.json",
    )
    assert (tmp_path / "audit.md").exists()
    quality = json.loads((tmp_path / "audit.json").read_text(encoding="utf-8"))
    assert quality["fixture_count"] == 760
    assert quality["live_claim_allowed"] is False

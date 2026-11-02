"""Manifest-integrity and freshness/completeness-gate tests, entirely synthetic
(tmp_path) — none depend on the real fetched cache, so they run identically with or
without it present.

S02 Stage A: an independent reviewer reproduced a real defect in the S01 contract — a
current season with a FEW recent missing results (well within the 14-day staleness
bound) still returned `current_season_publishable = True`, because that field only
ever checked staleness, not presence, of missing results. "Recent missing outcomes are
still missing outcomes." The six numbered tests below are the specific regression
tests requested for that fix; see docs/DATA_CONTRACT.md for the full field contract.
"""

from __future__ import annotations

import hashlib
import json
from datetime import date, timedelta
from pathlib import Path

import pytest
from conftest import FULL_SEASON_END as _FULL_SEASON_END
from conftest import FULL_SEASON_TEXT as _FULL_SEASON_TEXT
from conftest import REAL_CANONICAL_NAMES as _REAL_CANONICAL_NAMES

from matchweek_intelligence.build_data_quality import DataQualityError, build_report

_SYNTHETIC_COMPLETE_SEASON = """\
= Synthetic League 2024/25

# Date       Fri Aug 16 2024 - Sun May 25 2025 (282d)
# Teams      20
# Matches    2

▪ Matchday 1
  Fri Aug 16 2024
    20:00  Home Team A             v Away Team A              1-0 (1-0)
    20:00  Home Team B             v Away Team B              2-2 (1-0)
"""

# as_of_date will be set to 2024-09-01: Aug 10 is scored, Aug 16 has no score and is
# 16 days before as_of (> 14-day bound -> stale); Sep 1 itself is exactly the as_of
# date, so it must be scheduled_future, never result_missing.
_SYNTHETIC_CURRENT_SEASON_WITH_GAP = """\
= Synthetic League 2026/27

# Date       Sat Aug 10 2024 - Sun May 25 2025 (282d)
# Teams      20
# Matches    3

▪ Matchday 1
  Sat Aug 10 2024
    20:00  Home Team A             v Away Team A              1-0 (1-0)

▪ Matchday 2
  Fri Aug 16 2024
    20:00  Home Team B             v Away Team B

▪ Matchday 3
  Sun Sep 1 2024
    20:00  Home Team C             v Away Team C
"""


def _write_manifested_file(raw_dir: Path, path: str, content: str) -> dict:
    content_bytes = content.encode("utf-8")
    full_path = raw_dir / path
    full_path.parent.mkdir(parents=True, exist_ok=True)
    full_path.write_bytes(content_bytes)
    return {
        "path": path,
        "sha256": hashlib.sha256(content_bytes).hexdigest(),
        "byte_count": len(content_bytes),
    }


def _report_for(raw_dir: Path, manifest_path: Path, path: str, text: str, as_of_date: date) -> dict:
    entry = _write_manifested_file(raw_dir, path, text)
    manifest_path.write_text(
        json.dumps({"source_repo": "x/y", "pinned_commit": "deadbeef", "files": [entry]}),
        encoding="utf-8",
    )
    report = build_report(raw_dir=raw_dir, manifest_path=manifest_path, as_of_date=as_of_date)
    return report["files"][0]


def test_build_report_fails_closed_when_manifest_is_missing(tmp_path):
    with pytest.raises(DataQualityError, match="manifest not found"):
        build_report(
            raw_dir=tmp_path / "raw",
            manifest_path=tmp_path / "does-not-exist.json",
            as_of_date=date(2026, 11, 2),
        )


def test_build_report_fails_closed_when_manifested_file_is_missing_on_disk(tmp_path):
    raw_dir = tmp_path / "raw"
    manifest_path = tmp_path / "manifest.json"
    entry = _write_manifested_file(raw_dir, "a.txt", _SYNTHETIC_COMPLETE_SEASON)
    (raw_dir / "a.txt").unlink()
    manifest_path.write_text(
        json.dumps({"source_repo": "x/y", "pinned_commit": "deadbeef", "files": [entry]}),
        encoding="utf-8",
    )
    with pytest.raises(DataQualityError, match="missing on disk"):
        build_report(raw_dir=raw_dir, manifest_path=manifest_path, as_of_date=date(2026, 11, 2))


def test_build_report_fails_closed_on_a_same_byte_length_tamper(tmp_path):
    raw_dir = tmp_path / "raw"
    manifest_path = tmp_path / "manifest.json"
    entry = _write_manifested_file(raw_dir, "a.txt", _SYNTHETIC_COMPLETE_SEASON)
    tampered = _SYNTHETIC_COMPLETE_SEASON.replace("Home Team A", "Home Team X", 1)
    assert len(tampered) == len(_SYNTHETIC_COMPLETE_SEASON)
    (raw_dir / "a.txt").write_text(tampered, encoding="utf-8")
    manifest_path.write_text(
        json.dumps({"source_repo": "x/y", "pinned_commit": "deadbeef", "files": [entry]}),
        encoding="utf-8",
    )
    with pytest.raises(DataQualityError, match="integrity check failed"):
        build_report(raw_dir=raw_dir, manifest_path=manifest_path, as_of_date=date(2026, 11, 2))


def test_unsupported_subformat_file_is_reported_not_parsed_not_guessed(tmp_path):
    raw_dir = tmp_path / "raw"
    manifest_path = tmp_path / "manifest.json"
    # A genuinely unknown (fourth) variant: no bullet-prefixed headers at all.
    unknown_format_text = (
        "= Synthetic League 2099/00\n\n"
        "# Date       Fri Aug 1 2099 - Sun May 1 2100 (282d)\n"
        "# Teams      20\n# Matches  1\n\n"
        "Round 1\nFri Aug 1 2099\n  20:00  Home : 1-0 : Away\n"
    )
    file_report = _report_for(
        raw_dir, manifest_path, "a.txt", unknown_format_text, date(2026, 11, 2)
    )
    assert file_report["parsed"] is False
    assert file_report["detected_subformat"] == "unknown"


def test_duplicate_grain_key_is_reported(tmp_path):
    raw_dir = tmp_path / "raw"
    manifest_path = tmp_path / "manifest.json"
    text = (
        "= Synthetic League 2024/25\n\n"
        "# Date       Fri Aug 16 2024 - Sun May 25 2025 (282d)\n"
        "# Teams      20\n# Matches    2\n\n"
        "▪ Matchday 1\n  Fri Aug 16 2024\n"
        "    20:00  Home Team A             v Away Team A              1-0 (1-0)\n"
        "    20:00  Home Team A             v Away Team A              1-0 (1-0)\n"
    )
    file_report = _report_for(raw_dir, manifest_path, "a.txt", text, date(2026, 11, 2))
    dupes = file_report["duplicate_grain_keys"]
    assert len(dupes) == 1
    assert dupes[0]["count"] == 2


# --- Stage A: the six numbered regression tests ------------------------------------


def test_i_reviewers_exact_recent_missing_results_counterexample_now_fails_closed(tmp_path):
    # Exactly the reproduced defect: 1 scored + 2 past-unscored fixtures, both well
    # within the 14-day staleness bound. The OLD `current_season_publishable` field
    # would have returned True here. The new fields must not.
    as_of = date(2024, 9, 10)
    text = """\
= Synthetic League 2026/27

# Date       Sat Aug 10 2024 - Sun May 25 2025 (282d)
# Teams      20
# Matches    3

▪ Matchday 1
  Sat Aug 10 2024
    20:00  Home Team A             v Away Team A              1-0 (1-0)

▪ Matchday 2
  Mon Sep 2 2024
    20:00  Home Team B             v Away Team B

▪ Matchday 3
  Wed Sep 4 2024
    20:00  Home Team C             v Away Team C
"""
    raw_dir, manifest_path = tmp_path / "raw", tmp_path / "manifest.json"
    file_report = _report_for(raw_dir, manifest_path, "a.txt", text, as_of)

    assert file_report["result_missing_count"] == 2
    assert file_report["stale_result_missing_count"] == 0  # neither exceeds 14 days
    assert file_report["current_results_coverage_sufficient"] is False
    assert file_report["historical_season_complete"] is False


def test_ii_a_genuinely_complete_historical_season_passes_historical_completeness(tmp_path):
    raw_dir, manifest_path = tmp_path / "raw", tmp_path / "manifest.json"
    as_of = _FULL_SEASON_END + timedelta(days=30)
    file_report = _report_for(
        raw_dir, manifest_path, "2024-25/1-premierleague.txt", _FULL_SEASON_TEXT, as_of
    )

    assert file_report["fixture_count"] == 380
    assert file_report["scored_count"] == 380
    assert file_report["round_robin_violations"] == []
    assert file_report["historical_season_complete"] is True
    assert file_report["current_results_coverage_sufficient"] is True


def test_iii_a_complete_historical_season_never_self_certifies_as_a_live_feed(tmp_path):
    raw_dir, manifest_path = tmp_path / "raw", tmp_path / "manifest.json"
    as_of = _FULL_SEASON_END + timedelta(days=30)
    file_report = _report_for(
        raw_dir, manifest_path, "2024-25/1-premierleague.txt", _FULL_SEASON_TEXT, as_of
    )

    assert file_report["historical_season_complete"] is True  # the contrast case
    assert file_report["live_claim_allowed"] is False
    assert (
        file_report["source_recency"]["status"]
        == "not_independently_verified_by_automated_pipeline"
    )


def test_iv_current_source_with_any_past_missing_result_is_blocked_even_within_14_days(tmp_path):
    # A near-complete current season: every fixture scored except exactly ONE, which
    # is only 2 days stale (nowhere near the 14-day bound).
    as_of = date(2024, 8, 18)
    text = """\
= Synthetic League 2026/27

# Date       Sat Aug 10 2024 - Sun May 25 2025 (282d)
# Teams      20
# Matches    2

▪ Matchday 1
  Sat Aug 10 2024
    20:00  Home Team A             v Away Team A              1-0 (1-0)

▪ Matchday 2
  Thu Aug 16 2024
    20:00  Home Team B             v Away Team B
"""
    raw_dir, manifest_path = tmp_path / "raw", tmp_path / "manifest.json"
    file_report = _report_for(raw_dir, manifest_path, "a.txt", text, as_of)

    assert file_report["result_missing_count"] == 1
    assert file_report["stale_result_missing_count"] == 0
    assert file_report["current_results_coverage_sufficient"] is False


def test_v_as_of_boundary_cases(tmp_path):
    raw_dir, manifest_path = tmp_path / "raw", tmp_path / "manifest.json"

    # A fixture dated exactly on as_of_date must be scheduled_future, never
    # result_missing, purely from the boundary comparison being strict (`<`).
    on_boundary_text = """\
= Synthetic League 2024/25

# Date       Fri Aug 16 2024 - Sun May 25 2025 (282d)
# Teams      20
# Matches    1

▪ Matchday 1
  Fri Aug 16 2024
    20:00  Home Team A             v Away Team A
"""
    file_report = _report_for(raw_dir, manifest_path, "a.txt", on_boundary_text, date(2024, 8, 16))
    assert file_report["result_missing_count"] == 0
    assert file_report["scheduled_future_count"] == 1

    # historical_season_complete requires season_end_date STRICTLY before as_of_date —
    # equal to it must not count as "past".
    raw_dir2, manifest_path2 = tmp_path / "raw2", tmp_path / "manifest2.json"
    file_report_eq = _report_for(
        raw_dir2,
        manifest_path2,
        "2024-25/1-premierleague.txt",
        _FULL_SEASON_TEXT,
        _FULL_SEASON_END,
    )
    assert file_report_eq["historical_season_complete"] is False

    raw_dir3, manifest_path3 = tmp_path / "raw3", tmp_path / "manifest3.json"
    file_report_after = _report_for(
        raw_dir3,
        manifest_path3,
        "2024-25/1-premierleague.txt",
        _FULL_SEASON_TEXT,
        _FULL_SEASON_END + timedelta(days=1),
    )
    assert file_report_after["historical_season_complete"] is True


def test_vi_duplicate_and_short_fixture_count_fail_historical_completeness_safely(tmp_path):
    raw_dir, manifest_path = tmp_path / "raw", tmp_path / "manifest.json"

    # (a) A season far short of 380 fixtures, fully scored: must never be "complete".
    short_text = _SYNTHETIC_COMPLETE_SEASON  # only 2 fixtures
    short_report = _report_for(
        raw_dir, manifest_path, "2024-25/1-premierleague.txt", short_text, date(2026, 11, 2)
    )
    assert short_report["fixture_count"] == 2
    assert short_report["historical_season_complete"] is False

    # (b) A duplicated fixture within an otherwise-380-fixture file: historical
    # completeness must fail even though the header still claims 380 matches.
    duplicated_text = _FULL_SEASON_TEXT.replace(
        f"{_REAL_CANONICAL_NAMES[0]}             v {_REAL_CANONICAL_NAMES[-1]}",
        f"{_REAL_CANONICAL_NAMES[1]}             v {_REAL_CANONICAL_NAMES[2]}",
        1,
    )
    raw_dir2, manifest_path2 = tmp_path / "raw2", tmp_path / "manifest2.json"
    dup_report = _report_for(
        raw_dir2,
        manifest_path2,
        "2024-25/1-premierleague.txt",
        duplicated_text,
        _FULL_SEASON_END + timedelta(days=30),
    )
    assert dup_report["fixture_count"] == 380  # header/count still says 380
    assert dup_report["round_robin_violations"] != []
    assert dup_report["historical_season_complete"] is False

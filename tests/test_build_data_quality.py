"""Manifest-integrity and freshness-gate tests, entirely synthetic (tmp_path) — none
depend on the real fetched cache, so they run identically with or without it present."""

from __future__ import annotations

import hashlib
import json
from datetime import date
from pathlib import Path

import pytest

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
    # Tamper with the file's content while keeping byte length identical.
    tampered = _SYNTHETIC_COMPLETE_SEASON.replace("Home Team A", "Home Team X", 1)
    assert len(tampered) == len(_SYNTHETIC_COMPLETE_SEASON)
    (raw_dir / "a.txt").write_text(tampered, encoding="utf-8")
    manifest_path.write_text(
        json.dumps({"source_repo": "x/y", "pinned_commit": "deadbeef", "files": [entry]}),
        encoding="utf-8",
    )
    with pytest.raises(DataQualityError, match="integrity check failed"):
        build_report(raw_dir=raw_dir, manifest_path=manifest_path, as_of_date=date(2026, 11, 2))


def test_complete_historical_season_is_publishable_with_zero_missing(tmp_path):
    raw_dir = tmp_path / "raw"
    manifest_path = tmp_path / "manifest.json"
    entry = _write_manifested_file(
        raw_dir, "2024-25/1-premierleague.txt", _SYNTHETIC_COMPLETE_SEASON
    )
    manifest_path.write_text(
        json.dumps({"source_repo": "x/y", "pinned_commit": "deadbeef", "files": [entry]}),
        encoding="utf-8",
    )
    report = build_report(
        raw_dir=raw_dir, manifest_path=manifest_path, as_of_date=date(2026, 11, 2)
    )
    file_report = report["files"][0]
    assert file_report["current_season_publishable"] is True
    assert file_report["result_missing_count"] == 0
    assert file_report["scored_count"] == 2


def test_stale_missing_results_block_current_season_publishable(tmp_path):
    raw_dir = tmp_path / "raw"
    manifest_path = tmp_path / "manifest.json"
    entry = _write_manifested_file(
        raw_dir, "2026-27/1-premierleague.txt", _SYNTHETIC_CURRENT_SEASON_WITH_GAP
    )
    manifest_path.write_text(
        json.dumps({"source_repo": "x/y", "pinned_commit": "deadbeef", "files": [entry]}),
        encoding="utf-8",
    )
    report = build_report(raw_dir=raw_dir, manifest_path=manifest_path, as_of_date=date(2024, 9, 1))
    file_report = report["files"][0]

    assert file_report["current_season_publishable"] is False
    assert file_report["result_missing_count"] == 1  # Aug 16 only
    assert file_report["stale_result_missing_count"] == 1
    assert file_report["stale_result_missing_dates"] == ["2024-08-16"]
    # Sep 1 is the as_of date itself: scheduled_future, never result_missing.
    assert file_report["scheduled_future_count"] == 1


def test_unsupported_subformat_file_is_reported_not_parsed_not_guessed(tmp_path):
    raw_dir = tmp_path / "raw"
    manifest_path = tmp_path / "manifest.json"
    regular_season_text = (
        "= England | Premier League 2025/26\n\n"
        "# Dates    Fri Aug 15 2025 - Sun May 24 2026 (282d)\n"
        "# Teams    20\n# Matches  380\n\n"
        "▪ Regular Season - 1\nFri Aug 15 2025\n"
        "  19:00   Liverpool  4-2 (1-0)  Bournemouth\n"
    )
    entry = _write_manifested_file(raw_dir, "2025-26/1-premierleague.txt", regular_season_text)
    manifest_path.write_text(
        json.dumps({"source_repo": "x/y", "pinned_commit": "deadbeef", "files": [entry]}),
        encoding="utf-8",
    )
    report = build_report(
        raw_dir=raw_dir, manifest_path=manifest_path, as_of_date=date(2026, 11, 2)
    )
    file_report = report["files"][0]
    assert file_report["parsed"] is False
    assert file_report["detected_subformat"] == "regular_season_scorer_annotated"


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
    entry = _write_manifested_file(raw_dir, "a.txt", text)
    manifest_path.write_text(
        json.dumps({"source_repo": "x/y", "pinned_commit": "deadbeef", "files": [entry]}),
        encoding="utf-8",
    )
    report = build_report(
        raw_dir=raw_dir, manifest_path=manifest_path, as_of_date=date(2026, 11, 2)
    )
    dupes = report["files"][0]["duplicate_grain_keys"]
    assert len(dupes) == 1
    assert dupes[0]["count"] == 2

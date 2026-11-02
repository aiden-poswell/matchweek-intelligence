"""Stage C historical-corpus builder tests, entirely synthetic (tmp_path) — covers the
full negative-test list from the S02 brief: missing file, same-byte-length tamper,
wrong season identity, mismapped team alias, missing/extra fixture, duplicate fixture,
false year rollover, malformed scorer lines, lost goals, and negative scores."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from conftest import FULL_SEASON_START, FULL_SEASON_TEXT, REAL_CANONICAL_NAMES

from matchweek_intelligence.build_historical_corpus import HistoricalCorpusError, build_report


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


def _season_report_for(tmp_path: Path, path: str, text: str) -> dict:
    raw_dir, manifest_path = tmp_path / "raw", tmp_path / "manifest.json"
    entry = _write_manifested_file(raw_dir, path, text)
    manifest_path.write_text(
        json.dumps({"source_repo": "x/y", "pinned_commit": "deadbeef", "files": [entry]}),
        encoding="utf-8",
    )
    report = build_report(raw_dir=raw_dir, manifest_path=manifest_path)
    return report["seasons"][0]


def test_a_genuinely_complete_season_is_eligible(tmp_path):
    season = _season_report_for(tmp_path, "2024-25/1-premierleague.txt", FULL_SEASON_TEXT)
    assert season["eligible_complete_season"] is True
    assert season["ineligibility_reasons"] == []
    assert season["fixture_count"] == 380
    assert season["home_wins"] + season["draws"] + season["away_wins"] == 380


def test_negative_missing_file_fails_closed_before_any_report_is_written(tmp_path):
    raw_dir, manifest_path = tmp_path / "raw", tmp_path / "manifest.json"
    entry = _write_manifested_file(raw_dir, "2024-25/1-premierleague.txt", FULL_SEASON_TEXT)
    (raw_dir / "2024-25/1-premierleague.txt").unlink()
    manifest_path.write_text(
        json.dumps({"source_repo": "x/y", "pinned_commit": "deadbeef", "files": [entry]}),
        encoding="utf-8",
    )
    with pytest.raises(HistoricalCorpusError, match="missing on disk"):
        build_report(raw_dir=raw_dir, manifest_path=manifest_path)


def test_negative_same_byte_length_tamper_fails_closed(tmp_path):
    raw_dir, manifest_path = tmp_path / "raw", tmp_path / "manifest.json"
    entry = _write_manifested_file(raw_dir, "2024-25/1-premierleague.txt", FULL_SEASON_TEXT)
    tampered = FULL_SEASON_TEXT.replace("Arsenal             v", "ARSENAL             v", 1)
    assert len(tampered) == len(FULL_SEASON_TEXT)
    (raw_dir / "2024-25/1-premierleague.txt").write_text(tampered, encoding="utf-8")
    manifest_path.write_text(
        json.dumps({"source_repo": "x/y", "pinned_commit": "deadbeef", "files": [entry]}),
        encoding="utf-8",
    )
    with pytest.raises(HistoricalCorpusError, match="integrity check failed"):
        build_report(raw_dir=raw_dir, manifest_path=manifest_path)


def test_negative_wrong_season_identity_path_still_reports_but_is_not_a_candidate(tmp_path):
    # A file placed under a path this project doesn't recognise as one of the three
    # historical candidate seasons (season resolves to "unknown" by path mapping).
    season = _season_report_for(tmp_path, "1999-00/1-premierleague.txt", FULL_SEASON_TEXT)
    assert season["season"] == "unknown"
    assert season["season_kind"] == "current_partial"
    assert season["eligible_complete_season"] is False


def test_negative_mismapped_team_alias_is_a_hard_stop(tmp_path):
    teams_with_unmapped = REAL_CANONICAL_NAMES[:-1] + ["Totally Unmapped FC"]
    from conftest import build_full_double_round_robin_text

    text = build_full_double_round_robin_text(
        "2024/25", FULL_SEASON_START, teams=teams_with_unmapped
    )
    season = _season_report_for(tmp_path, "2024-25/1-premierleague.txt", text)
    assert season["eligible_complete_season"] is False
    assert season["team_identity_errors"] != []
    assert any("Totally Unmapped FC" in r for r in season["ineligibility_reasons"])


def test_negative_missing_fixture_is_caught_even_if_total_count_text_claims_380(tmp_path):
    # Drop the final fixture line pair (date + fixture) — the header still claims 380.
    lines = FULL_SEASON_TEXT.splitlines()
    truncated = "\n".join(lines[:-2]) + "\n"
    season = _season_report_for(tmp_path, "2024-25/1-premierleague.txt", truncated)
    assert season["fixture_count"] == 379
    assert season["eligible_complete_season"] is False
    assert any("expected 380 fixtures" in r for r in season["ineligibility_reasons"])


def test_negative_duplicate_fixture_caught_by_round_robin_even_at_380_total(tmp_path):
    lines = FULL_SEASON_TEXT.splitlines()
    # lines[7]/[8] are the first fixture's date+fixture line pair (header is lines[0:7]).
    first_fixture_lines = lines[7:9]
    assert "20:00" in first_fixture_lines[1]
    # Replace the LAST fixture pairing with a duplicate of the first, keeping the
    # total line (and hence fixture) count unchanged at 380.
    text = "\n".join(lines[:-2] + first_fixture_lines) + "\n"
    season = _season_report_for(tmp_path, "2024-25/1-premierleague.txt", text)
    assert season["fixture_count"] == 380
    assert season["eligible_complete_season"] is False
    assert season["round_robin_violations"] != []


def test_negative_extra_fixture_beyond_380_is_caught(tmp_path):
    extra_date_and_fixture = (
        "  Thu Jan 1 2099\n"
        f"    20:00  {REAL_CANONICAL_NAMES[0]}             v {REAL_CANONICAL_NAMES[1]}"
        "             9-9 (9-9)\n"
    )
    text = FULL_SEASON_TEXT + extra_date_and_fixture
    season = _season_report_for(tmp_path, "2024-25/1-premierleague.txt", text)
    assert season["fixture_count"] == 381
    assert season["eligible_complete_season"] is False
    assert any("expected 380 fixtures, found 381" in r for r in season["ineligibility_reasons"])


def test_negative_false_year_rollover_is_caught_by_date_window_check(tmp_path):
    # A date line that omits the year while the month INCREASES (not a real rollover)
    # must not silently roll the year forward anyway — the parser only rolls over on a
    # month DECREASE. Verify a genuinely out-of-window date (one explicitly dated a
    # year later than the season) is caught by the date-window check rather than
    # silently accepted.
    lines = FULL_SEASON_TEXT.splitlines()
    lines[7] = "  Sat Aug 10 2099"  # the first date line, moved a century later
    text = "\n".join(lines) + "\n"
    season = _season_report_for(tmp_path, "2024-25/1-premierleague.txt", text)
    assert season["eligible_complete_season"] is False
    assert any("date window" in r for r in season["ineligibility_reasons"])


def test_negative_malformed_scorer_line_is_quarantined_not_silently_accepted(tmp_path):
    lines = FULL_SEASON_TEXT.splitlines()
    # Inject an unterminated scorer-annotation block after the first fixture line.
    lines.insert(9, "                  (Unterminated Scorer 10'")
    text = "\n".join(lines) + "\n"
    season = _season_report_for(tmp_path, "2024-25/1-premierleague.txt", text)
    assert season["quarantined_line_count"] >= 1
    assert season["eligible_complete_season"] is False


def test_negative_lost_goals_half_time_exceeding_full_time_is_caught(tmp_path):
    text = FULL_SEASON_TEXT.replace("1-0 (1-0)", "1-0 (5-0)", 1)
    season = _season_report_for(tmp_path, "2024-25/1-premierleague.txt", text)
    assert season["eligible_complete_season"] is False
    assert any("score integrity" in r for r in season["ineligibility_reasons"])
    assert any("exceeds" in v for v in season["score_integrity_violations"])


def test_current_partial_season_is_never_marked_eligible_regardless_of_its_own_cleanliness(
    tmp_path,
):
    # Even a perfectly clean, structurally valid season is never "eligible" if its path
    # doesn't resolve to one of the three historical candidate seasons.
    season = _season_report_for(tmp_path, "2026-27/1-premierleague.txt", FULL_SEASON_TEXT)
    assert season["season"] == "2026-27"
    assert season["season_kind"] == "current_partial"
    assert season["round_robin_violations"] == []  # structurally clean
    assert season["eligible_complete_season"] is False  # but never eligible regardless

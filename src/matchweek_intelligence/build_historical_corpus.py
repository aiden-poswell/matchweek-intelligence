"""Build the Stage C historical-corpus quality report.

For each of 2023/24, 2024/25 and 2025/26 independently, a season is only marked
`eligible_complete_season = true` when ALL of the following hold — not fixture count
alone:

1. Exactly 380 unique fixtures, 20 distinct canonically-mapped teams, 380 scored,
   zero result_missing, zero quarantine, zero duplicate match-grain keys.
2. The full 20-team double round-robin pairing matrix validates (19 home + 19 away per
   club; exactly one home-and-away fixture per opponent pair) — this rejects a missing,
   duplicated, or reversed pairing even when the total still happens to be 380.
3. Nonnegative integer scores; half-time goals never exceed full-time goals; every
   match date falls inside the season's own declared calendar window.
4. No unmapped team name (`team_identity.UnmappedTeamNameError` is caught and recorded
   as a hard-stop reason, never silently skipped).

A season failing any of these is reported as ineligible with the SPECIFIC reasons —
never silently dropped and never marked complete on fixture count alone. This module
writes no file at all if the source manifest fails its own integrity check first.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path

from matchweek_intelligence.corpus_validation import validate_date_window, validate_scores
from matchweek_intelligence.fetch import DEFAULT_MANIFEST_PATH, DEFAULT_RAW_DIR
from matchweek_intelligence.football_txt import (
    SUPPORTED_SUBFORMATS,
    UnsupportedFootballTxtFormatError,
    detect_subformat,
    parse_football_txt,
)
from matchweek_intelligence.season_structure import EXPECTED_FIXTURES, validate_double_round_robin
from matchweek_intelligence.team_identity import UnmappedTeamNameError, canonical_team_name

DEFAULT_OUTPUT_PATH = Path("reports/s02_historical_corpus_quality.json")

_SEASON_BY_PATH = {
    "2023-24/1-premierleague.txt": "2023-24",
    "2024-25/1-premierleague.txt": "2024-25",
    "2025-26/1-premierleague.txt": "2025-26",
    "2026-27/1-premierleague.txt": "2026-27",
}
_HISTORICAL_CANDIDATE_SEASONS = frozenset({"2023-24", "2024-25", "2025-26"})

# Fixtures are evaluated as-of a date well past every historical season's end, since
# eligibility here is about the SEASON's own completeness, not any particular as-of
# replay date. This is a fixed, documented constant for this report only — later
# modelling slices use their own as-of cutoffs via chronology.py, never this one.
_CORPUS_AS_OF_DATE_ISO = "2027-01-01"


class HistoricalCorpusError(RuntimeError):
    """Raised when the source manifest itself fails integrity verification."""


def _verify_manifest(manifest: dict, raw_dir: Path) -> None:
    for entry in manifest["files"]:
        local_path = raw_dir / entry["path"]
        if not local_path.exists():
            raise HistoricalCorpusError(f"manifested file missing on disk: {local_path}")
        content = local_path.read_bytes()
        actual_hash = hashlib.sha256(content).hexdigest()
        if actual_hash != entry["sha256"]:
            raise HistoricalCorpusError(
                f"integrity check failed for {local_path}: "
                f"manifest sha256={entry['sha256']}, actual={actual_hash}"
            )


def _season_report(path: str, text: str, as_of_date) -> dict:
    season = _SEASON_BY_PATH.get(path, "unknown")
    season_kind = (
        "historical_candidate" if season in _HISTORICAL_CANDIDATE_SEASONS else "current_partial"
    )
    subformat = detect_subformat(text)

    if subformat not in SUPPORTED_SUBFORMATS:
        return {
            "season": season,
            "path": path,
            "season_kind": season_kind,
            "parsed": False,
            "eligible_complete_season": False,
            "ineligibility_reasons": [f"unsupported sub-format: {subformat}"],
        }

    try:
        result = parse_football_txt(text, "premier-league", season, as_of_date)
    except UnsupportedFootballTxtFormatError as exc:
        return {
            "season": season,
            "path": path,
            "season_kind": season_kind,
            "parsed": False,
            "eligible_complete_season": False,
            "ineligibility_reasons": [str(exc)],
        }

    reasons: list[str] = []

    team_identity_errors: list[str] = []
    round_robin_violations: list[str] = []
    try:
        canonical_by_raw = {
            raw: canonical_team_name(raw)
            for raw in {r.home_team_raw for r in result.records}
            | {r.away_team_raw for r in result.records}
        }
    except UnmappedTeamNameError as exc:
        team_identity_errors.append(str(exc))
        reasons.append(f"unmapped team name: {exc}")
    else:
        round_robin_violations = validate_double_round_robin(
            result.records, team_of=lambda raw: canonical_by_raw[raw]
        )
        reasons.extend(f"round-robin: {v}" for v in round_robin_violations)

    scored = [r for r in result.records if r.status == "played_with_score"]
    missing = [r for r in result.records if r.status == "result_missing"]
    future = [r for r in result.records if r.status == "scheduled_future"]

    seen: Counter = Counter(
        (r.match_date.isoformat(), r.home_team_raw, r.away_team_raw) for r in result.records
    )
    duplicate_keys = [
        {"match_date": k[0], "home_team_raw": k[1], "away_team_raw": k[2], "count": v}
        for k, v in sorted(seen.items())
        if v > 1
    ]

    score_violations = validate_scores(result.records)
    date_window_violations = (
        validate_date_window(result.records, result.season_start_date, result.season_end_date)
        if result.season_start_date and result.season_end_date
        else ["season start/end date could not be determined"]
    )

    if len(result.records) != EXPECTED_FIXTURES:
        reasons.append(f"expected {EXPECTED_FIXTURES} fixtures, found {len(result.records)}")
    if len(scored) != len(result.records):
        reasons.append(f"not all fixtures are scored: {len(scored)}/{len(result.records)}")
    if missing:
        reasons.append(f"{len(missing)} fixture(s) have a missing result")
    if result.quarantined:
        reasons.append(f"{len(result.quarantined)} quarantined line(s)")
    if duplicate_keys:
        reasons.append(f"{len(duplicate_keys)} duplicate match-grain key(s)")
    reasons.extend(f"score integrity: {v}" for v in score_violations)
    reasons.extend(f"date window: {v}" for v in date_window_violations)

    home_wins = sum(1 for r in scored if r.home_score > r.away_score)
    draws = sum(1 for r in scored if r.home_score == r.away_score)
    away_wins = sum(1 for r in scored if r.home_score < r.away_score)

    eligible = season_kind == "historical_candidate" and not reasons

    return {
        "season": season,
        "path": path,
        "season_kind": season_kind,
        "parsed": True,
        "detected_subformat": subformat,
        "season_start_date": result.season_start_date.isoformat()
        if result.season_start_date
        else None,
        "season_end_date": result.season_end_date.isoformat() if result.season_end_date else None,
        "fixture_count": len(result.records),
        "scored_count": len(scored),
        "result_missing_count": len(missing),
        "scheduled_future_count": len(future),
        "quarantined_line_count": len(result.quarantined),
        "duplicate_grain_keys": duplicate_keys,
        "team_identity_errors": team_identity_errors,
        "round_robin_violations": round_robin_violations,
        "score_integrity_violations": score_violations,
        "date_window_violations": date_window_violations,
        "home_wins": home_wins,
        "draws": draws,
        "away_wins": away_wins,
        "eligible_complete_season": eligible,
        "ineligibility_reasons": []
        if eligible
        else (reasons or ["not a historical candidate season"]),
    }


def build_report(
    raw_dir: Path = DEFAULT_RAW_DIR, manifest_path: Path = DEFAULT_MANIFEST_PATH
) -> dict:
    from datetime import date as _date

    if not manifest_path.exists():
        raise HistoricalCorpusError(f"manifest not found: {manifest_path} — run fetch first")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    _verify_manifest(manifest, raw_dir)

    as_of_date = _date.fromisoformat(_CORPUS_AS_OF_DATE_ISO)
    seasons = []
    for entry in manifest["files"]:
        text = (raw_dir / entry["path"]).read_text(encoding="utf-8")
        seasons.append(_season_report(entry["path"], text, as_of_date))

    return {
        "source_repo": manifest["source_repo"],
        "pinned_commit": manifest["pinned_commit"],
        "corpus_as_of_date": _CORPUS_AS_OF_DATE_ISO,
        "seasons": seasons,
    }


def write_report(report: dict, output_path: Path = DEFAULT_OUTPUT_PATH) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> None:
    report = build_report()
    write_report(report)
    for s in report["seasons"]:
        if s.get("parsed"):
            print(
                f"{s['season']} ({s['season_kind']}): "
                f"eligible_complete_season={s['eligible_complete_season']}"
            )
            for reason in s["ineligibility_reasons"]:
                print(f"    - {reason}")
        else:
            print(f"{s['season']}: NOT PARSED — {s['ineligibility_reasons']}")


if __name__ == "__main__":
    main()

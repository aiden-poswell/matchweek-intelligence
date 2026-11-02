"""Build reports/s01_data_quality.json from the fetched, manifest-verified raw files.

Verifies each raw file's SHA-256 against reports/s01_source_manifest.json before
trusting its content (a manifest check, not a refetch) — this is the integrity gate the
brief asked for: "catches a same-byte-length tamper and missing source." Any file whose
hash does not match, or is simply absent, fails this CLI closed rather than silently
skipping it.

S02 freshness/completeness contract (replacing S01's single, structurally fail-open
`current_season_publishable` field)
---------------------------------------------------------------------------------------
An independent reviewer reproduced a real defect in the S01 field: on a synthetic
current season with 1 scored + 2 past-unscored fixtures dated LESS than 14 days ago,
`current_season_publishable = len(stale_missing) == 0` returned True — "recent missing
outcomes are still missing outcomes." The field was also misleadingly True (vacuously)
on the complete 2024/25 file, which could be read as a stronger claim than "no stale
rows" actually supports. That field is removed. It is replaced by three deliberately
separated booleans, documented in docs/DATA_CONTRACT.md:

- `historical_season_complete`: True only when the season has the expected 380
  fixtures, every one is scored, the fixture list passes the full double round-robin
  structural check (season_structure.validate_double_round_robin), there is zero
  quarantine/duplication, AND the season's own declared end date is strictly before
  as_of_date. A season still in progress can never satisfy this, regardless of how
  clean its scored-so-far rows are.
- `current_results_coverage_sufficient`: True only when there is no evidenced gap —
  zero result_missing rows, zero quarantine, zero duplicates, and the full fixture list
  (played and not-yet-played) still passes the round-robin structural check. This is
  deliberately NOT "the season is complete" — a season with zero matches played yet
  trivially satisfies it, which is correct: the field means "no missing-result gap has
  been found," not "enough of the season has happened to model."
- `live_claim_allowed`: hard-coded `False`, unconditionally, in this module. Per-file
  "is this source still being actively updated" provenance requires an external
  GitHub commit-history check (`gh api repos/.../commits?path=...`) — see
  docs/SOURCE_RIGHTS_AND_PROVENANCE.md section 1d for how that was done by hand for
  2026/27 (last real update found: 2026-09-21). That fact is NOT re-derivable from the
  raw file's bytes alone, so this pipeline never self-certifies freshness; `source_recency`
  below records this honestly as "not independently verified" rather than guessing.
  A frozen pinned-commit snapshot is valid for historical as-of replay forever — it must
  never become "live" merely because every match in it happened to be scored by some
  earlier as-of date.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from datetime import date
from pathlib import Path

from matchweek_intelligence.fetch import DEFAULT_MANIFEST_PATH, DEFAULT_RAW_DIR
from matchweek_intelligence.football_txt import (
    SUPPORTED_SUBFORMATS,
    UnsupportedFootballTxtFormatError,
    detect_subformat,
    parse_football_txt,
)
from matchweek_intelligence.season_structure import EXPECTED_FIXTURES, validate_double_round_robin
from matchweek_intelligence.team_identity import UnmappedTeamNameError, canonical_team_name

DEFAULT_OUTPUT_PATH = Path("reports/s01_data_quality.json")
STALE_RESULT_MISSING_DAYS = 14

_SEASON_BY_PATH = {
    "2023-24/1-premierleague.txt": "2023-24",
    "2024-25/1-premierleague.txt": "2024-25",
    "2025-26/1-premierleague.txt": "2025-26",
    "2026-27/1-premierleague.txt": "2026-27",
}


class DataQualityError(RuntimeError):
    """Raised when a manifested file is missing or fails its integrity check."""


def _verify_manifest(manifest: dict, raw_dir: Path) -> None:
    for entry in manifest["files"]:
        local_path = raw_dir / entry["path"]
        if not local_path.exists():
            raise DataQualityError(f"manifested file missing on disk: {local_path}")
        content = local_path.read_bytes()
        actual_hash = hashlib.sha256(content).hexdigest()
        if actual_hash != entry["sha256"]:
            raise DataQualityError(
                f"integrity check failed for {local_path}: "
                f"manifest sha256={entry['sha256']}, actual={actual_hash}"
            )
        if len(content) != entry["byte_count"]:
            raise DataQualityError(
                f"byte-count mismatch for {local_path}: "
                f"manifest={entry['byte_count']}, actual={len(content)}"
            )


def _duplicate_keys(records) -> list[dict]:
    seen: dict[tuple, int] = {}
    for r in records:
        key = (r.match_date.isoformat(), r.home_team_raw, r.away_team_raw)
        seen[key] = seen.get(key, 0) + 1
    dupes = {k: v for k, v in seen.items() if v > 1}
    return [
        {"match_date": k[0], "home_team_raw": k[1], "away_team_raw": k[2], "count": v}
        for k, v in sorted(dupes.items())
    ]


_SOURCE_RECENCY_NOT_VERIFIED = {
    "status": "not_independently_verified_by_automated_pipeline",
    "note": (
        "Per-file last-real-update provenance requires an external GitHub "
        "commit-history check, not derivable from file bytes alone — see "
        "docs/SOURCE_RIGHTS_AND_PROVENANCE.md section 1d. This pipeline never "
        "self-certifies freshness."
    ),
}


def _file_report(path: str, text: str, as_of_date: date) -> dict:
    subformat = detect_subformat(text)
    if subformat not in SUPPORTED_SUBFORMATS:
        return {
            "path": path,
            "parsed": False,
            "detected_subformat": subformat,
            "reason": "schema variant not supported by this project's parser — see "
            "docs/SOURCE_RIGHTS_AND_PROVENANCE.md section 1b / reports/S02_FORMAT_AUDIT.md",
        }

    season = _SEASON_BY_PATH.get(path, "unknown")
    try:
        result = parse_football_txt(text, "premier-league", season, as_of_date)
    except UnsupportedFootballTxtFormatError as exc:
        return {"path": path, "parsed": False, "detected_subformat": subformat, "reason": str(exc)}

    scored = [r for r in result.records if r.status == "played_with_score"]
    missing = [r for r in result.records if r.status == "result_missing"]
    future = [r for r in result.records if r.status == "scheduled_future"]
    dupes = _duplicate_keys(result.records)
    stale_missing = [
        r for r in missing if (as_of_date - r.match_date).days > STALE_RESULT_MISSING_DAYS
    ]

    team_identity_errors: list[str] = []
    round_robin_violations: list[str] | None = None
    try:
        canonical_by_raw = {
            raw: canonical_team_name(raw)
            for raw in {r.home_team_raw for r in result.records}
            | {r.away_team_raw for r in result.records}
        }
    except UnmappedTeamNameError as exc:
        team_identity_errors.append(str(exc))
    else:
        round_robin_violations = validate_double_round_robin(
            result.records, team_of=lambda raw: canonical_by_raw[raw]
        )

    structurally_clean = (
        len(result.quarantined) == 0
        and dupes == []
        and not team_identity_errors
        and round_robin_violations == []
    )

    historical_season_complete = (
        len(result.records) == EXPECTED_FIXTURES
        and len(scored) == len(result.records)
        and len(missing) == 0
        and len(future) == 0
        and structurally_clean
        and result.season_end_date is not None
        and result.season_end_date < as_of_date
    )
    current_results_coverage_sufficient = len(missing) == 0 and structurally_clean

    report = {
        "path": path,
        "parsed": True,
        "detected_subformat": subformat,
        "season": season,
        "as_of_date": as_of_date.isoformat(),
        "season_start_date": result.season_start_date.isoformat()
        if result.season_start_date
        else None,
        "season_end_date": result.season_end_date.isoformat() if result.season_end_date else None,
        "fixture_count": len(result.records),
        "scored_count": len(scored),
        "result_missing_count": len(missing),
        "scheduled_future_count": len(future),
        "quarantined_line_count": len(result.quarantined),
        "quarantined_lines": [asdict(q) for q in result.quarantined],
        "duplicate_grain_keys": dupes,
        "team_identity_errors": team_identity_errors,
        "round_robin_violations": round_robin_violations,
        "earliest_scored_date": min((r.match_date.isoformat() for r in scored), default=None),
        "latest_scored_date": max((r.match_date.isoformat() for r in scored), default=None),
        "earliest_scheduled_future_date": min(
            (r.match_date.isoformat() for r in future), default=None
        ),
        "result_missing_dates": sorted({r.match_date.isoformat() for r in missing}),
        "stale_result_missing_count": len(stale_missing),
        "stale_result_missing_dates": sorted({r.match_date.isoformat() for r in stale_missing}),
        "historical_season_complete": historical_season_complete,
        "current_results_coverage_sufficient": current_results_coverage_sufficient,
        "source_recency": _SOURCE_RECENCY_NOT_VERIFIED,
        "live_claim_allowed": False,
    }
    return report


def build_report(
    raw_dir: Path = DEFAULT_RAW_DIR,
    manifest_path: Path = DEFAULT_MANIFEST_PATH,
    as_of_date: date | None = None,
) -> dict:
    if not manifest_path.exists():
        raise DataQualityError(f"manifest not found: {manifest_path} — run fetch first")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    _verify_manifest(manifest, raw_dir)

    effective_as_of = as_of_date or date.today()
    file_reports = []
    for entry in manifest["files"]:
        text = (raw_dir / entry["path"]).read_text(encoding="utf-8")
        file_reports.append(_file_report(entry["path"], text, effective_as_of))

    return {
        "as_of_date": effective_as_of.isoformat(),
        "source_repo": manifest["source_repo"],
        "pinned_commit": manifest["pinned_commit"],
        "files": file_reports,
    }


def write_report(report: dict, output_path: Path = DEFAULT_OUTPUT_PATH) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> None:
    report = build_report()
    write_report(report)
    for f in report["files"]:
        if f["parsed"]:
            print(
                f"{f['path']}: {f['scored_count']}/{f['fixture_count']} scored, "
                f"historical_season_complete={f['historical_season_complete']}, "
                f"current_results_coverage_sufficient={f['current_results_coverage_sufficient']}"
            )
        else:
            print(f"{f['path']}: NOT PARSED ({f['detected_subformat']})")


if __name__ == "__main__":
    main()

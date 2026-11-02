"""Build reports/s01_data_quality.json from the fetched, manifest-verified raw files.

Verifies each raw file's SHA-256 against reports/s01_source_manifest.json before
trusting its content (a manifest check, not a refetch) — this is the integrity gate the
brief asked for: "catches a same-byte-length tamper and missing source." Any file whose
hash does not match, or is simply absent, fails this CLI closed rather than silently
skipping it.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from datetime import date
from pathlib import Path

from matchweek_intelligence.fetch import DEFAULT_MANIFEST_PATH, DEFAULT_RAW_DIR
from matchweek_intelligence.football_txt import (
    SUPPORTED_SUBFORMAT,
    UnsupportedFootballTxtFormatError,
    detect_subformat,
    parse_football_txt,
)

DEFAULT_OUTPUT_PATH = Path("reports/s01_data_quality.json")
STALE_RESULT_MISSING_DAYS = 14

_SEASON_BY_PATH = {
    "2024-25/1-premierleague.txt": "2024-25",
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
    dupes: dict[tuple, int] = {}
    for r in records:
        key = (r.match_date.isoformat(), r.home_team_raw, r.away_team_raw)
        seen[key] = seen.get(key, 0) + 1
    for key, count in seen.items():
        if count > 1:
            dupes[key] = count
    return [
        {"match_date": k[0], "home_team_raw": k[1], "away_team_raw": k[2], "count": v}
        for k, v in sorted(dupes.items())
    ]


def _file_report(path: str, text: str, as_of_date: date) -> dict:
    subformat = detect_subformat(text)
    if subformat != SUPPORTED_SUBFORMAT:
        return {
            "path": path,
            "parsed": False,
            "detected_subformat": subformat,
            "reason": "schema variant not supported by this slice's parser — see "
            "docs/SOURCE_RIGHTS_AND_PROVENANCE.md section 1b",
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

    report = {
        "path": path,
        "parsed": True,
        "detected_subformat": subformat,
        "season": season,
        "as_of_date": as_of_date.isoformat(),
        "fixture_count": len(result.records),
        "scored_count": len(scored),
        "result_missing_count": len(missing),
        "scheduled_future_count": len(future),
        "quarantined_line_count": len(result.quarantined),
        "quarantined_lines": [asdict(q) for q in result.quarantined],
        "duplicate_grain_keys": dupes,
        "earliest_scored_date": min((r.match_date.isoformat() for r in scored), default=None),
        "latest_scored_date": max((r.match_date.isoformat() for r in scored), default=None),
        "earliest_scheduled_future_date": min(
            (r.match_date.isoformat() for r in future), default=None
        ),
        "result_missing_dates": sorted({r.match_date.isoformat() for r in missing}),
        "stale_result_missing_count": len(stale_missing),
        "stale_result_missing_dates": sorted({r.match_date.isoformat() for r in stale_missing}),
        "current_season_publishable": len(stale_missing) == 0,
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
                f"current_season_publishable={f['current_season_publishable']}"
            )
        else:
            print(f"{f['path']}: NOT PARSED ({f['detected_subformat']})")


if __name__ == "__main__":
    main()

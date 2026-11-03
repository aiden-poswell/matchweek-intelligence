"""Canonical, leak-free model-facing input loader.

Loads the three S02-verified eligible historical seasons (2023/24, 2024/25, 2025/26) from
the pinned-commit raw cache, REVALIDATING — not merely re-reading — the full round-robin
structure, score integrity, calendar-window, and canonical team mapping for each season
before returning anything. Fails closed on any unknown team, duplicate fixture, invalid
date, missing/incorrect manifest entry, or missing score. 2026/27 is never loaded by this
module, regardless of caller input — it is not in `ELIGIBLE_SEASONS` and there is no
parameter that can add it.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from matchweek_intelligence.corpus_validation import validate_date_window, validate_scores
from matchweek_intelligence.fetch import DEFAULT_MANIFEST_PATH, DEFAULT_RAW_DIR
from matchweek_intelligence.football_txt import (
    SUPPORTED_SUBFORMATS,
    UnsupportedFootballTxtFormatError,
    detect_subformat,
    parse_football_txt,
)
from matchweek_intelligence.season_structure import validate_double_round_robin
from matchweek_intelligence.team_identity import UnmappedTeamNameError, canonical_team_name

ELIGIBLE_SEASONS: tuple[str, ...] = ("2023-24", "2024-25", "2025-26")

_SEASON_BY_PATH = {
    "2023-24/1-premierleague.txt": "2023-24",
    "2024-25/1-premierleague.txt": "2024-25",
    "2025-26/1-premierleague.txt": "2025-26",
    "2026-27/1-premierleague.txt": "2026-27",
}

# Same fixed analytical sentinel as build_historical_corpus.py: chosen only to be safely
# past every historical season's own declared end date, so a fully-scored season is never
# accidentally treated as having a "scheduled_future" row. This is NOT a live/current date
# and grants no permission to use 2026/27 (which is excluded by ELIGIBLE_SEASONS regardless
# of this constant) — see reports/S03_PROTOCOL_ALIGNMENT.md section 4.
_CORPUS_AS_OF_DATE = date(2027, 1, 1)


class ModelInputError(RuntimeError):
    """Raised when the model-facing corpus cannot be safely built."""


@dataclass(frozen=True)
class ModelRecord:
    competition: str
    season: str
    match_date: date
    home_team: str  # canonical, via team_identity.canonical_team_name
    away_team: str  # canonical
    home_score: int
    away_score: int
    status: str  # always "played_with_score" for a record returned by this module
    source_line_no: int


def _verify_manifest(manifest: dict, raw_dir: Path) -> None:
    for entry in manifest["files"]:
        local_path = raw_dir / entry["path"]
        if not local_path.exists():
            raise ModelInputError(f"manifested file missing on disk: {local_path}")
        content = local_path.read_bytes()
        actual_hash = hashlib.sha256(content).hexdigest()
        if actual_hash != entry["sha256"]:
            raise ModelInputError(
                f"integrity check failed for {local_path}: "
                f"manifest sha256={entry['sha256']}, actual={actual_hash}"
            )
        if len(content) != entry["byte_count"]:
            raise ModelInputError(
                f"byte-count mismatch for {local_path}: "
                f"manifest={entry['byte_count']}, actual={len(content)}"
            )


def _load_and_validate_season(path: str, text: str) -> list[ModelRecord]:
    season = _SEASON_BY_PATH.get(path)
    if season not in ELIGIBLE_SEASONS:
        raise ModelInputError(f"{path}: does not resolve to an eligible historical season")

    subformat = detect_subformat(text)
    if subformat not in SUPPORTED_SUBFORMATS:
        raise ModelInputError(f"{path}: unsupported sub-format {subformat!r}")
    try:
        result = parse_football_txt(text, "premier-league", season, _CORPUS_AS_OF_DATE)
    except UnsupportedFootballTxtFormatError as exc:
        raise ModelInputError(f"{path}: {exc}") from exc

    if result.quarantined:
        raise ModelInputError(
            f"{path}: {len(result.quarantined)} quarantined line(s) — cannot build model input"
        )

    try:
        canonical_by_raw = {
            raw: canonical_team_name(raw)
            for raw in {r.home_team_raw for r in result.records}
            | {r.away_team_raw for r in result.records}
        }
    except UnmappedTeamNameError as exc:
        raise ModelInputError(f"{path}: {exc}") from exc

    def team_of(raw: str) -> str:
        return canonical_by_raw[raw]

    round_robin_violations = validate_double_round_robin(result.records, team_of=team_of)
    if round_robin_violations:
        raise ModelInputError(
            f"{path}: {len(round_robin_violations)} round-robin violation(s): "
            f"{round_robin_violations[:3]}"
        )

    score_violations = validate_scores(result.records)
    if score_violations:
        raise ModelInputError(f"{path}: score integrity violations: {score_violations[:3]}")

    if result.season_start_date is None or result.season_end_date is None:
        raise ModelInputError(f"{path}: season start/end date could not be determined")
    date_violations = validate_date_window(
        result.records, result.season_start_date, result.season_end_date
    )
    if date_violations:
        raise ModelInputError(f"{path}: date-window violations: {date_violations[:3]}")

    seen: set[tuple] = set()
    for r in result.records:
        key = (r.match_date, team_of(r.home_team_raw), team_of(r.away_team_raw))
        if key in seen:
            raise ModelInputError(f"{path}: duplicate match-grain key {key}")
        seen.add(key)

    model_records: list[ModelRecord] = []
    for r in result.records:
        if r.status != "played_with_score" or r.home_score is None or r.away_score is None:
            raise ModelInputError(
                f"{path}: fixture {r.match_date} {r.home_team_raw} v {r.away_team_raw} "
                "has no score — eligible historical seasons must be fully scored"
            )
        model_records.append(
            ModelRecord(
                competition=r.competition,
                season=r.season,
                match_date=r.match_date,
                home_team=team_of(r.home_team_raw),
                away_team=team_of(r.away_team_raw),
                home_score=r.home_score,
                away_score=r.away_score,
                status=r.status,
                source_line_no=r.source_line_no,
            )
        )
    return model_records


def load_eligible_historical_records(
    raw_dir: Path = DEFAULT_RAW_DIR, manifest_path: Path = DEFAULT_MANIFEST_PATH
) -> list[ModelRecord]:
    """Load, revalidate, and return every fixture from the three eligible historical
    seasons (2023/24, 2024/25, 2025/26 — 2026/27 is never included), sorted
    deterministically by (match_date, home_team, away_team) for a reproducible audit
    order — never by source-file position or round/matchday label.
    """
    if not manifest_path.exists():
        raise ModelInputError(f"manifest not found: {manifest_path} — run fetch first")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    _verify_manifest(manifest, raw_dir)

    all_records: list[ModelRecord] = []
    seasons_found: set[str] = set()
    for entry in manifest["files"]:
        season = _SEASON_BY_PATH.get(entry["path"])
        if season not in ELIGIBLE_SEASONS:
            continue
        text = (raw_dir / entry["path"]).read_text(encoding="utf-8")
        all_records.extend(_load_and_validate_season(entry["path"], text))
        seasons_found.add(season)

    missing_seasons = set(ELIGIBLE_SEASONS) - seasons_found
    if missing_seasons:
        raise ModelInputError(
            f"eligible season(s) not found in manifest: {sorted(missing_seasons)}"
        )

    all_records.sort(key=lambda r: (r.match_date, r.home_team, r.away_team))
    return all_records

"""Score-integrity and calendar-window checks, independent of round-robin structure.

The parser's own score regex only ever matches `\\d+-\\d+` (no sign), so a negative score
cannot be represented after parsing — these checks still assert that explicitly rather
than silently trusting the parser never to regress. Date-window checks never infer that
a match "must have occurred" from its date falling inside the season span; they only
check that a date the source itself claims is consistent with the season boundaries the
source itself declared.
"""

from __future__ import annotations

from datetime import date

from matchweek_intelligence.football_txt import MatchRecord


def validate_scores(records: list[MatchRecord]) -> list[str]:
    problems: list[str] = []
    for r in records:
        for label, value in (
            ("home_score", r.home_score),
            ("away_score", r.away_score),
            ("home_score_ht", r.home_score_ht),
            ("away_score_ht", r.away_score_ht),
        ):
            if value is not None and value < 0:
                problems.append(
                    f"{r.match_date} {r.home_team_raw} v {r.away_team_raw}: "
                    f"negative {label}={value}"
                )
        if r.home_score_ht is not None and r.home_score is not None:
            if r.home_score_ht > r.home_score:
                problems.append(
                    f"{r.match_date} {r.home_team_raw} v {r.away_team_raw}: "
                    f"home HT {r.home_score_ht} exceeds home FT {r.home_score}"
                )
        if r.away_score_ht is not None and r.away_score is not None:
            if r.away_score_ht > r.away_score:
                problems.append(
                    f"{r.match_date} {r.home_team_raw} v {r.away_team_raw}: "
                    f"away HT {r.away_score_ht} exceeds away FT {r.away_score}"
                )
    return problems


def validate_date_window(
    records: list[MatchRecord], season_start: date, season_end: date
) -> list[str]:
    problems: list[str] = []
    for r in records:
        if r.match_date < season_start or r.match_date > season_end:
            problems.append(
                f"{r.match_date} {r.home_team_raw} v {r.away_team_raw}: "
                f"outside declared season window {season_start}..{season_end}"
            )
    return problems

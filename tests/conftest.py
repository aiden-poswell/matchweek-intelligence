"""Shared synthetic-corpus helpers used by multiple test modules.

Centralised here so test_build_data_quality.py and test_build_historical_corpus.py
build the exact same kind of genuinely-complete, structurally-valid synthetic season
rather than two subtly different hand-rolled generators drifting apart.
"""

from __future__ import annotations

from datetime import date, timedelta

# 20 real, VALID RAW team-name strings (each a real key in team_identity.py's mapping
# table). "Chelsea" and "Southampton" (bare, no suffix) are deliberately NOT used —
# real extraction found no file where either is ever printed without "FC", so neither
# bare form is a valid raw key (see team_identity.py's module docstring).
REAL_CANONICAL_NAMES = [
    "Arsenal",
    "Aston Villa",
    "Bournemouth",
    "Brentford",
    "Brighton & Hove Albion",
    "Burnley",
    "Chelsea FC",
    "Crystal Palace",
    "Everton",
    "Fulham",
    "Leeds United",
    "Liverpool",
    "Manchester City",
    "Manchester United",
    "Newcastle United",
    "Nottingham Forest",
    "Southampton FC",
    "Tottenham Hotspur",
    "West Ham United",
    "Wolverhampton Wanderers",
]
assert len(REAL_CANONICAL_NAMES) == 20

_WEEKDAY_ABBRS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
_MONTH_ABBRS = [
    "Jan",
    "Feb",
    "Mar",
    "Apr",
    "May",
    "Jun",
    "Jul",
    "Aug",
    "Sep",
    "Oct",
    "Nov",
    "Dec",
]


def format_date_line(d: date) -> str:
    # Deliberately avoids strftime's "%-d" (no-leading-zero day), a glibc/Linux-only
    # extension not portable to Windows.
    return f"{_WEEKDAY_ABBRS[d.weekday()]} {_MONTH_ABBRS[d.month - 1]} {d.day} {d.year}"


def build_full_double_round_robin_text(
    season_header: str, start: date, teams: list[str] | None = None
) -> str:
    """A genuinely complete, structurally valid 380-fixture season, "matchday_v_literal"
    style, one fixture per calendar day. The declared header end date matches the
    actual last fixture's date (379 days after `start`), so `season_end_date` stays
    internally consistent with the real parsed rows.
    """
    team_list = teams if teams is not None else REAL_CANONICAL_NAMES
    end = start + timedelta(days=379)
    lines = [
        f"= Synthetic League {season_header}",
        "",
        f"# Date       {format_date_line(start)} - {format_date_line(end)} (380d)",
        "# Teams      20",
        "# Matches    380",
        "",
        "▪ Matchday 1",
    ]
    day_offset = 0
    for home in team_list:
        for away in team_list:
            if home == away:
                continue
            match_date = start + timedelta(days=day_offset)
            lines.append(f"  {format_date_line(match_date)}")
            lines.append(f"    20:00  {home}             v {away}             1-0 (1-0)")
            day_offset += 1
    return "\n".join(lines) + "\n"


FULL_SEASON_START = date(2024, 8, 10)
FULL_SEASON_TEXT = build_full_double_round_robin_text("2024/25", FULL_SEASON_START)
FULL_SEASON_END = FULL_SEASON_START + timedelta(days=379)

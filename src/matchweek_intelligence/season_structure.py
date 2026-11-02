"""Structural validation of a season's fixture list against the expected 20-team
double round-robin shape (38 fixtures/club: 19 home, 19 away; exactly one home-and-away
pairing per opponent). This checks the FIXTURE LIST itself, independent of whether
results are scored yet — a current/partial season's source file already lists all 380
fixtures (future ones included, unscored), so this check applies to it too.

A header claiming "380 matches" is not an actual row-count check — this module counts
the real parsed rows and the real pairing matrix, and flags anything that disagrees,
including a duplicated, missing, or reversed (home/away swapped) fixture even when the
total count happens to still be 380.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable

from matchweek_intelligence.football_txt import MatchRecord

EXPECTED_TEAMS = 20
EXPECTED_FIXTURES = EXPECTED_TEAMS * (EXPECTED_TEAMS - 1)  # 380
EXPECTED_HOME_FIXTURES_PER_TEAM = EXPECTED_TEAMS - 1  # 19
EXPECTED_AWAY_FIXTURES_PER_TEAM = EXPECTED_TEAMS - 1  # 19


def validate_double_round_robin(
    records: list[MatchRecord], team_of: Callable[[str], str] | None = None
) -> list[str]:
    """Return a list of violation strings (empty means structurally valid).

    `team_of` optionally maps a record's raw home/away label to a canonicalised team
    identity before counting. Callers whose records already carry canonical labels in
    `home_team_raw`/`away_team_raw` can omit it.
    """
    resolve = team_of or (lambda name: name)

    def home_id(r: MatchRecord) -> str:
        return resolve(r.home_team_raw)

    def away_id(r: MatchRecord) -> str:
        return resolve(r.away_team_raw)

    problems: list[str] = []

    if len(records) != EXPECTED_FIXTURES:
        problems.append(f"expected {EXPECTED_FIXTURES} fixtures, found {len(records)}")

    teams: set[str] = set()
    for r in records:
        teams.add(home_id(r))
        teams.add(away_id(r))
    if len(teams) != EXPECTED_TEAMS:
        problems.append(
            f"expected {EXPECTED_TEAMS} distinct teams, found {len(teams)}: {sorted(teams)}"
        )

    home_counts = Counter(home_id(r) for r in records)
    away_counts = Counter(away_id(r) for r in records)
    for team in sorted(teams):
        home_n = home_counts.get(team, 0)
        away_n = away_counts.get(team, 0)
        if home_n != EXPECTED_HOME_FIXTURES_PER_TEAM:
            problems.append(
                f"{team}: expected {EXPECTED_HOME_FIXTURES_PER_TEAM} home fixtures, found {home_n}"
            )
        if away_n != EXPECTED_AWAY_FIXTURES_PER_TEAM:
            problems.append(
                f"{team}: expected {EXPECTED_AWAY_FIXTURES_PER_TEAM} away fixtures, found {away_n}"
            )

    pairing_counts = Counter((home_id(r), away_id(r)) for r in records)
    for home in sorted(teams):
        for away in sorted(teams):
            if home == away:
                continue
            count = pairing_counts.get((home, away), 0)
            if count != 1:
                problems.append(
                    f"{home} (home) v {away} (away): expected exactly 1 fixture, found {count}"
                )

    return problems

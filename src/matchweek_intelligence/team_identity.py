"""Canonical team identity mapping, built only from direct evidence.

Team-name spelling is NOT consistent across the four season files this project
ingests. Direct extraction of every (home, away) label actually present in
2023-24/1-premierleague.txt, 2024-25/1-premierleague.txt, 2025-26/1-premierleague.txt and
2026-27/1-premierleague.txt (pinned commit 9ee7a0c351805c99cc334478a9bf04b7d0432fec) found
46 distinct raw strings for what are, by direct football-world knowledge of these specific
clubs, 27 distinct real clubs. Notable real findings from that extraction (recorded here,
not assumed):

- 2023/24, 2024/25 and 2026/27 consistently suffix every club with "FC" (or "AFC" for
  clubs whose actual name includes it, e.g. "Hull City AFC", "Sunderland AFC") except
  "AFC Bournemouth", where AFC is a genuine name PREFIX, not a generic suffix.
- 2025/26 drops the "FC"/"AFC" suffix for every club EXCEPT Chelsea, which is
  consistently printed "Chelsea FC" throughout that single file (38 occurrences,
  0 occurrences of a bare "Chelsea") — a genuine within-file inconsistency, not a
  transcription error on this project's part.

This is therefore an explicit, reviewed, hand-built lookup table — never a suffix-stripping
regex and never a fuzzy/similarity join. Any raw name encountered that is NOT in this table
raises `UnmappedTeamNameError` rather than being guessed at, and the caller is expected to
treat that as a hard stop on building the historical corpus (see
reports/S02_HISTORICAL_CORPUS_AUDIT.md).
"""

from __future__ import annotations

# raw_name -> canonical_name. Built from direct extraction of all four pinned season
# files; see the module docstring above for the real inconsistencies this accounts for.
_CANONICAL_TEAM_NAMES: dict[str, str] = {
    "AFC Bournemouth": "Bournemouth",
    "Bournemouth": "Bournemouth",
    "Arsenal FC": "Arsenal",
    "Arsenal": "Arsenal",
    "Aston Villa FC": "Aston Villa",
    "Aston Villa": "Aston Villa",
    "Brentford FC": "Brentford",
    "Brentford": "Brentford",
    "Brighton & Hove Albion FC": "Brighton & Hove Albion",
    "Brighton & Hove Albion": "Brighton & Hove Albion",
    "Burnley FC": "Burnley",
    "Burnley": "Burnley",
    "Chelsea FC": "Chelsea",
    "Coventry City FC": "Coventry City",
    "Crystal Palace FC": "Crystal Palace",
    "Crystal Palace": "Crystal Palace",
    "Everton FC": "Everton",
    "Everton": "Everton",
    "Fulham FC": "Fulham",
    "Fulham": "Fulham",
    "Hull City AFC": "Hull City",
    "Ipswich Town FC": "Ipswich Town",
    "Leeds United FC": "Leeds United",
    "Leeds United": "Leeds United",
    "Leicester City FC": "Leicester City",
    "Liverpool FC": "Liverpool",
    "Liverpool": "Liverpool",
    "Luton Town FC": "Luton Town",
    "Manchester City FC": "Manchester City",
    "Manchester City": "Manchester City",
    "Manchester United FC": "Manchester United",
    "Manchester United": "Manchester United",
    "Newcastle United FC": "Newcastle United",
    "Newcastle United": "Newcastle United",
    "Nottingham Forest FC": "Nottingham Forest",
    "Nottingham Forest": "Nottingham Forest",
    "Sheffield United FC": "Sheffield United",
    "Southampton FC": "Southampton",
    "Sunderland AFC": "Sunderland",
    "Sunderland": "Sunderland",
    "Tottenham Hotspur FC": "Tottenham Hotspur",
    "Tottenham Hotspur": "Tottenham Hotspur",
    "West Ham United FC": "West Ham United",
    "West Ham United": "West Ham United",
    "Wolverhampton Wanderers FC": "Wolverhampton Wanderers",
    "Wolverhampton Wanderers": "Wolverhampton Wanderers",
}


class UnmappedTeamNameError(RuntimeError):
    """Raised when a raw team label has no reviewed canonical mapping.

    This is a hard stop, not something to guess around: an unmapped name means either a
    genuinely new club this table hasn't been reviewed for, or a many-to-one collision
    risk that must be resolved by a human before the historical corpus is built.
    """

    def __init__(self, raw_name: str):
        self.raw_name = raw_name
        super().__init__(
            f"no reviewed canonical mapping for team name {raw_name!r} — "
            "add it to team_identity._CANONICAL_TEAM_NAMES only after confirming "
            "which real club it is, never by fuzzy matching"
        )


def canonical_team_name(raw_name: str) -> str:
    try:
        return _CANONICAL_TEAM_NAMES[raw_name]
    except KeyError:
        raise UnmappedTeamNameError(raw_name) from None


def known_raw_names() -> frozenset[str]:
    return frozenset(_CANONICAL_TEAM_NAMES)

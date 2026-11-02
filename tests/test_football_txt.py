"""Parser tests using real excerpts (copied verbatim from the fetched 2024/25 source) and
synthetic edge cases for behaviour the real excerpts don't happen to exercise."""

from datetime import date

import pytest

from matchweek_intelligence.football_txt import (
    SUPPORTED_SUBFORMAT,
    UnsupportedFootballTxtFormatError,
    detect_subformat,
    parse_football_txt,
)

# Verbatim excerpt from openfootball/england, pinned commit
# 9ee7a0c351805c99cc334478a9bf04b7d0432fec, 2024-25/1-premierleague.txt lines 1-21.
REAL_EXCERPT_MATCHDAY_1 = """\
= English Premier League 2024/25

# Date       Fri Aug 16 2024 - Sun May 25 2025 (282d)
# Teams      20
# Matches    380



▪ Matchday 1
  Fri Aug 16 2024
    20:00  Manchester United FC    v Fulham FC                1-0 (0-0)
  Sat Aug 17
    12:30  Ipswich Town FC         v Liverpool FC             0-2 (0-0)
    15:00  Arsenal FC              v Wolverhampton Wanderers FC  2-0 (1-0)
           Everton FC              v Brighton & Hove Albion FC  0-3 (0-1)
           Newcastle United FC     v Southampton FC           1-0 (1-0)
           Nottingham Forest FC    v AFC Bournemouth          1-1 (1-0)
    17:30  West Ham United FC      v Aston Villa FC           1-2 (1-1)
  Sun Aug 18
    14:00  Brentford FC            v Crystal Palace FC        2-1 (1-0)
    16:30  Chelsea FC              v Manchester City FC       0-2 (0-1)
"""

# Verbatim excerpt from the same file, lines 296-318: the real Dec 2024 -> Jan 2025
# calendar-year boundary, where the source itself reprints the year explicitly on the
# first January date line.
REAL_EXCERPT_YEAR_BOUNDARY = """\
= English Premier League 2024/25

# Date       Fri Aug 16 2024 - Sun May 25 2025 (282d)
# Teams      20
# Matches    380

▪ Matchday 19
  Mon Dec 30 2024
    19:45  Aston Villa FC          v Brighton & Hove Albion FC  2-2 (1-1)
           Ipswich Town FC         v Chelsea FC               2-0 (1-0)
    20:00  Manchester United FC    v Newcastle United FC      0-2 (0-2)
  Wed Jan 1 2025
    17:30  Brentford FC            v Arsenal FC               1-3 (1-1)

▪ Matchday 20
  Sat Jan 4
    12:30  Tottenham Hotspur FC    v Newcastle United FC      1-2 (1-2)
"""

# Verbatim excerpt from 2026-27/1-premierleague.txt Matchday 6: real unplayed fixtures
# (no score at all), including one with the score omitted entirely.
REAL_EXCERPT_UNPLAYED = """\
= English Premier League 2026/27

# Date       Fri Aug 21 2026 - Sun May 30 2027 (282d)
# Teams      20
# Matches    380

▪ Matchday 6
  Sat Oct 10 2026
    12:30  Arsenal FC              v Leeds United FC
    15:00  Sunderland AFC          v Brighton & Hove Albion FC
"""

# Verbatim excerpt from 2025-26/1-premierleague.txt — the real, different sub-format
# this slice's parser must detect and reject, never guess-parse.
REAL_EXCERPT_REGULAR_SEASON_SUBFORMAT = """\
= England | Premier League 2025/26

# Dates    Fri Aug 15 2025 - Sun May 24 2026 (282d)
# Teams    20
# Matches  380

▪ Regular Season - 1
Fri Aug 15 2025
  19:00   Liverpool  4-2 (1-0)  Bournemouth
"""

# Verbatim excerpt from 2023-24/1-premierleague.txt — a third real sub-format
# ("Matchday" header, but no literal " v " separator).
REAL_EXCERPT_MATCHDAY_NO_V_SUBFORMAT = """\
= English Premier League 2023/24

# Date       Fri Aug 11 2023 - Sun May 19 2024 (282d)
# Teams      20
# Matches    380

▪ Matchday 1
Fri Aug 11
  20:00  Burnley FC               0-3 (0-2)  Manchester City FC
"""


def test_detects_supported_subformat_from_real_excerpt():
    assert detect_subformat(REAL_EXCERPT_MATCHDAY_1) == SUPPORTED_SUBFORMAT


def test_detects_regular_season_subformat_as_unsupported():
    assert (
        detect_subformat(REAL_EXCERPT_REGULAR_SEASON_SUBFORMAT) == "regular_season_scorer_annotated"
    )


def test_detects_matchday_no_v_subformat_as_unsupported():
    assert detect_subformat(REAL_EXCERPT_MATCHDAY_NO_V_SUBFORMAT) == "matchday_no_v_literal"


def test_parse_raises_on_unsupported_subformat_rather_than_guessing():
    with pytest.raises(UnsupportedFootballTxtFormatError) as exc_info:
        parse_football_txt(
            REAL_EXCERPT_REGULAR_SEASON_SUBFORMAT, "premier-league", "2025-26", date(2026, 11, 2)
        )
    assert exc_info.value.detected_subformat == "regular_season_scorer_annotated"

    with pytest.raises(UnsupportedFootballTxtFormatError) as exc_info_2:
        parse_football_txt(
            REAL_EXCERPT_MATCHDAY_NO_V_SUBFORMAT, "premier-league", "2023-24", date(2026, 11, 2)
        )
    assert exc_info_2.value.detected_subformat == "matchday_no_v_literal"


def test_parses_real_scored_fixtures_correctly():
    result = parse_football_txt(
        REAL_EXCERPT_MATCHDAY_1, "premier-league", "2024-25", date(2026, 11, 2)
    )
    assert len(result.records) == 9
    assert result.quarantined == []

    first = result.records[0]
    assert first.match_date == date(2024, 8, 16)
    assert first.home_team_raw == "Manchester United FC"
    assert first.away_team_raw == "Fulham FC"
    assert (first.home_score, first.away_score) == (1, 0)
    assert (first.home_score_ht, first.away_score_ht) == (0, 0)
    assert first.status == "played_with_score"
    assert first.raw_round_label == "Matchday 1"

    # A continuation fixture line with no leading kickoff time still attaches to the
    # same date and parses correctly.
    everton_row = next(r for r in result.records if r.home_team_raw == "Everton FC")
    assert everton_row.match_date == date(2024, 8, 17)
    assert (everton_row.home_score, everton_row.away_score) == (0, 3)


def test_never_turns_a_missing_score_into_a_draw():
    result = parse_football_txt(
        REAL_EXCERPT_UNPLAYED, "premier-league", "2026-27", date(2026, 11, 2)
    )
    assert len(result.records) == 2
    for record in result.records:
        assert record.home_score is None
        assert record.away_score is None
        assert record.status in ("result_missing", "scheduled_future")


def test_past_unplayed_fixture_is_result_missing_not_played():
    # Oct 10 2026 is in the past relative to as_of_date 2026-11-02.
    result = parse_football_txt(
        REAL_EXCERPT_UNPLAYED, "premier-league", "2026-27", date(2026, 11, 2)
    )
    assert all(r.status == "result_missing" for r in result.records)
    # Flip the as_of date to before the fixture: now it must be scheduled_future, never
    # "played" and never defaulted to a score, purely because the date has passed.
    result_before = parse_football_txt(
        REAL_EXCERPT_UNPLAYED, "premier-league", "2026-27", date(2026, 9, 1)
    )
    assert all(r.status == "scheduled_future" for r in result_before.records)


def test_real_year_boundary_rollover_with_explicit_source_year():
    result = parse_football_txt(
        REAL_EXCERPT_YEAR_BOUNDARY, "premier-league", "2024-25", date(2026, 11, 2)
    )
    dates_by_team = {r.home_team_raw: r.match_date for r in result.records}
    assert dates_by_team["Aston Villa FC"] == date(2024, 12, 30)
    assert dates_by_team["Brentford FC"] == date(2025, 1, 1)
    assert dates_by_team["Tottenham Hotspur FC"] == date(2025, 1, 4)


def test_synthetic_year_rollover_without_explicit_year_on_the_jan_line():
    # Defensive branch: a file that (unlike the real one) omits the year even on the
    # first January date line. The parser must still infer the rollover from the
    # season-span header rather than staying on the start year.
    text = """\
= Synthetic League 2024/25

# Date       Fri Aug 16 2024 - Sun May 25 2025 (282d)
# Teams      20
# Matches    2

▪ Matchday 1
  Mon Dec 30
    20:00  Home Team A             v Away Team A              1-0 (1-0)
  Wed Jan 1
    17:30  Home Team B             v Away Team B              2-0 (1-0)
"""
    result = parse_football_txt(text, "synthetic", "2024-25", date(2026, 1, 1))
    dates_by_team = {r.home_team_raw: r.match_date for r in result.records}
    assert dates_by_team["Home Team A"] == date(2024, 12, 30)
    assert dates_by_team["Home Team B"] == date(2025, 1, 1)


def test_malformed_fixture_line_is_quarantined_not_dropped_silently():
    text = """\
= Synthetic League 2024/25

# Date       Fri Aug 16 2024 - Sun May 25 2025 (282d)
# Teams      20
# Matches    1

▪ Matchday 1
  Fri Aug 16 2024
    20:00  v Only One Side Present
"""
    result = parse_football_txt(text, "synthetic", "2024-25", date(2026, 1, 1))
    assert result.records == []
    assert len(result.quarantined) == 1
    assert result.quarantined[0].reason == "fixture line did not parse"


def test_fixture_line_before_any_date_header_is_quarantined():
    text = """\
= Synthetic League 2024/25

# Date       Fri Aug 16 2024 - Sun May 25 2025 (282d)
# Teams      20
# Matches    1

▪ Matchday 1
    20:00  Home Team A             v Away Team A              1-0 (1-0)
"""
    result = parse_football_txt(text, "synthetic", "2024-25", date(2026, 1, 1))
    assert result.records == []
    assert len(result.quarantined) == 1
    assert "before any date header" in result.quarantined[0].reason


def test_missing_half_time_score_is_null_not_equal_to_full_time():
    text = """\
= Synthetic League 2024/25

# Date       Fri Aug 16 2024 - Sun May 25 2025 (282d)
# Teams      20
# Matches    1

▪ Matchday 1
  Fri Aug 16 2024
    20:00  Home Team A             v Away Team A              0-0
"""
    result = parse_football_txt(text, "synthetic", "2024-25", date(2026, 1, 1))
    assert len(result.records) == 1
    record = result.records[0]
    assert (record.home_score, record.away_score) == (0, 0)
    assert record.home_score_ht is None
    assert record.away_score_ht is None


def test_round_label_is_not_unique_and_is_carried_through_as_informational():
    text = """\
= Synthetic League 2024/25

# Date       Fri Aug 16 2024 - Sun May 25 2025 (282d)
# Teams      20
# Matches    2

▪ Matchday 5
  Fri Aug 16 2024
    20:00  Home Team A             v Away Team A              1-0 (1-0)

▪ Matchday 4
  Sat Aug 17 2024
    15:00  Home Team B             v Away Team B              2-0 (1-0)

▪ Matchday 5
  Wed Sep 4 2024
    20:00  Home Team C             v Away Team C              0-0
"""
    result = parse_football_txt(text, "synthetic", "2024-25", date(2026, 1, 1))
    round_labels = [r.raw_round_label for r in result.records]
    assert round_labels.count("Matchday 5") == 2
    assert round_labels == ["Matchday 5", "Matchday 4", "Matchday 5"]

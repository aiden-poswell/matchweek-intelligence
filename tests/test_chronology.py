"""Proves the as-of chronological cutoff never leaks future or same-day information."""

from datetime import date

from matchweek_intelligence.chronology import as_of_filter
from matchweek_intelligence.football_txt import MatchRecord


def _record(match_date: date, home: str, away: str, scored: bool = True) -> MatchRecord:
    return MatchRecord(
        competition="premier-league",
        season="2024-25",
        match_date=match_date,
        raw_round_label="Matchday 1",
        home_team_raw=home,
        away_team_raw=away,
        home_score=1 if scored else None,
        away_score=0 if scored else None,
        home_score_ht=0 if scored else None,
        away_score_ht=0 if scored else None,
        status="played_with_score" if scored else "scheduled_future",
        source_line_no=1,
    )


def test_excludes_future_matches_relative_to_cutoff():
    records = [
        _record(date(2024, 8, 16), "A", "B"),
        _record(date(2024, 8, 23), "C", "D"),
        _record(date(2024, 9, 1), "E", "F"),
    ]
    filtered = as_of_filter(records, cutoff_date=date(2024, 8, 24))
    assert [r.home_team_raw for r in filtered] == ["A", "C"]


def test_excludes_same_day_fixtures_as_a_whole_batch():
    # Two fixtures on the cutoff date itself must both be excluded — there is no
    # reliable kickoff-time field in this source to decide one happened "before" the
    # other on the same calendar day.
    records = [
        _record(date(2024, 8, 16), "A", "B"),
        _record(date(2024, 8, 23), "C", "D"),
        _record(date(2024, 8, 23), "E", "F"),
    ]
    filtered = as_of_filter(records, cutoff_date=date(2024, 8, 23))
    assert [r.home_team_raw for r in filtered] == ["A"]


def test_empty_cutoff_window_excludes_everything():
    records = [_record(date(2024, 8, 16), "A", "B")]
    assert as_of_filter(records, cutoff_date=date(2024, 1, 1)) == []


def test_cutoff_after_all_matches_keeps_everything():
    records = [
        _record(date(2024, 8, 16), "A", "B"),
        _record(date(2024, 8, 23), "C", "D"),
    ]
    filtered = as_of_filter(records, cutoff_date=date(2025, 1, 1))
    assert len(filtered) == 2

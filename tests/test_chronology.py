"""Proves the as-of chronological cutoff never leaks future or same-day information,
and that the model-facing helper additionally never leaks a scoreless row."""

from datetime import date

from matchweek_intelligence.chronology import as_of_filter, completed_training_results_as_of
from matchweek_intelligence.football_txt import MatchRecord


def _record(
    match_date: date, home: str, away: str, scored: bool = True, status: str | None = None
) -> MatchRecord:
    resolved_status = status or ("played_with_score" if scored else "scheduled_future")
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
        status=resolved_status,
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


def test_as_of_filter_alone_can_still_return_a_result_missing_row():
    # This is the exact gap completed_training_results_as_of exists to close: a
    # result_missing row IS chronologically before the cutoff, so as_of_filter alone
    # lets it through.
    missing = _record(date(2024, 8, 16), "A", "B", scored=False, status="result_missing")
    filtered = as_of_filter([missing], cutoff_date=date(2024, 9, 1))
    assert filtered == [missing]


def test_completed_training_results_as_of_excludes_a_result_missing_row_despite_its_past_date():
    scored = _record(date(2024, 8, 16), "A", "B", scored=True)
    missing = _record(date(2024, 8, 23), "C", "D", scored=False, status="result_missing")
    filtered = completed_training_results_as_of([scored, missing], cutoff_date=date(2024, 9, 1))
    assert [r.home_team_raw for r in filtered] == ["A"]


def test_completed_training_results_as_of_still_excludes_future_and_same_day_rows():
    scored_past = _record(date(2024, 8, 16), "A", "B", scored=True)
    scored_on_cutoff = _record(date(2024, 8, 23), "C", "D", scored=True)
    scored_future = _record(date(2024, 9, 1), "E", "F", scored=True)
    filtered = completed_training_results_as_of(
        [scored_past, scored_on_cutoff, scored_future], cutoff_date=date(2024, 8, 23)
    )
    assert [r.home_team_raw for r in filtered] == ["A"]

from datetime import date

from matchweek_intelligence.corpus_validation import validate_date_window, validate_scores
from matchweek_intelligence.football_txt import MatchRecord


def _record(**overrides) -> MatchRecord:
    base = dict(
        competition="synthetic",
        season="2024-25",
        match_date=date(2024, 9, 1),
        raw_round_label="Matchday 1",
        home_team_raw="Home",
        away_team_raw="Away",
        home_score=2,
        away_score=1,
        home_score_ht=1,
        away_score_ht=0,
        status="played_with_score",
        source_line_no=1,
    )
    base.update(overrides)
    return MatchRecord(**base)


def test_valid_scores_produce_no_violations():
    assert validate_scores([_record()]) == []


def test_half_time_exceeding_full_time_is_flagged_for_home_and_away_independently():
    home_bad = _record(home_score=1, home_score_ht=2)
    violations = validate_scores([home_bad])
    assert len(violations) == 1
    assert "home HT 2 exceeds home FT 1" in violations[0]

    away_bad = _record(away_score=0, away_score_ht=1)
    violations = validate_scores([away_bad])
    assert len(violations) == 1
    assert "away HT 1 exceeds away FT 0" in violations[0]


def test_negative_score_is_flagged_even_though_the_parser_cannot_produce_one():
    # Defence in depth: the real parser's regex cannot emit a negative value, but this
    # check must still catch one if a record is ever constructed another way.
    bad = _record(home_score=-1)
    violations = validate_scores([bad])
    assert any("negative home_score=-1" in v for v in violations)


def test_null_half_time_scores_never_trigger_a_false_violation():
    record = _record(home_score_ht=None, away_score_ht=None)
    assert validate_scores([record]) == []


def test_date_within_season_window_has_no_violation():
    record = _record(match_date=date(2024, 9, 1))
    violations = validate_date_window([record], date(2024, 8, 1), date(2025, 5, 31))
    assert violations == []


def test_date_before_season_start_is_flagged():
    record = _record(match_date=date(2024, 7, 1))
    violations = validate_date_window([record], date(2024, 8, 1), date(2025, 5, 31))
    assert len(violations) == 1
    assert "outside declared season window" in violations[0]


def test_date_after_season_end_is_flagged():
    record = _record(match_date=date(2025, 6, 15))
    violations = validate_date_window([record], date(2024, 8, 1), date(2025, 5, 31))
    assert len(violations) == 1


def test_dates_exactly_on_the_boundary_are_not_flagged():
    start, end = date(2024, 8, 1), date(2025, 5, 31)
    records = [_record(match_date=start), _record(match_date=end)]
    assert validate_date_window(records, start, end) == []

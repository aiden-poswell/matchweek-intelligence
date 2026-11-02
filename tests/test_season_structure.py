"""Round-robin structural validator tests — entirely synthetic, built to prove each
failure mode independently (missing, duplicated, and reversed fixtures all caught even
when the total fixture count still happens to be right in the cases where that's
possible to construct)."""

from datetime import date, timedelta

from matchweek_intelligence.football_txt import MatchRecord
from matchweek_intelligence.season_structure import (
    EXPECTED_FIXTURES,
    validate_double_round_robin,
)

_TEAMS = [f"Team {i:02d}" for i in range(20)]


def _make_valid_double_round_robin() -> list[MatchRecord]:
    records = []
    start = date(2024, 8, 10)
    day = 0
    for home in _TEAMS:
        for away in _TEAMS:
            if home == away:
                continue
            records.append(
                MatchRecord(
                    competition="synthetic",
                    season="2024-25",
                    match_date=start + timedelta(days=day),
                    raw_round_label="Matchday X",
                    home_team_raw=home,
                    away_team_raw=away,
                    home_score=1,
                    away_score=0,
                    home_score_ht=0,
                    away_score_ht=0,
                    status="played_with_score",
                    source_line_no=day + 1,
                )
            )
            day += 1
    return records


def test_a_genuinely_valid_double_round_robin_has_zero_violations():
    records = _make_valid_double_round_robin()
    assert len(records) == EXPECTED_FIXTURES == 380
    assert validate_double_round_robin(records) == []


def test_missing_fixture_is_caught_even_though_this_shrinks_the_total():
    records = _make_valid_double_round_robin()[:-1]  # drop the last fixture
    violations = validate_double_round_robin(records)
    assert any("expected 380 fixtures, found 379" in v for v in violations)
    assert any("expected exactly 1 fixture, found 0" in v for v in violations)


def test_duplicated_fixture_is_caught_even_though_total_count_is_restored_to_380():
    records = _make_valid_double_round_robin()
    # Remove a real fixture and duplicate a different one, keeping the total at 380.
    records = records[:-1]
    records.append(records[0])
    assert len(records) == EXPECTED_FIXTURES
    violations = validate_double_round_robin(records)
    assert any("found 2" in v for v in violations)  # the duplicated pairing
    assert any("found 0" in v for v in violations)  # the pairing that got dropped


def test_reversed_home_away_fixture_is_caught_even_though_total_count_stays_380():
    records = _make_valid_double_round_robin()
    # Reverse exactly one fixture's home/away assignment (simulating a transcription
    # error that keeps the same two teams and the same total count).
    victim = records[0]
    records[0] = MatchRecord(
        competition=victim.competition,
        season=victim.season,
        match_date=victim.match_date,
        raw_round_label=victim.raw_round_label,
        home_team_raw=victim.away_team_raw,
        away_team_raw=victim.home_team_raw,
        home_score=victim.home_score,
        away_score=victim.away_score,
        home_score_ht=victim.home_score_ht,
        away_score_ht=victim.away_score_ht,
        status=victim.status,
        source_line_no=victim.source_line_no,
    )
    assert len(records) == EXPECTED_FIXTURES
    violations = validate_double_round_robin(records)
    # The original (home, away) pairing is now missing; its reverse now appears twice.
    assert any("found 0" in v for v in violations)
    assert any("found 2" in v for v in violations)


def test_wrong_team_count_is_caught():
    records = [
        r
        for r in _make_valid_double_round_robin()
        if "Team 19" not in (r.home_team_raw, r.away_team_raw)
    ]
    violations = validate_double_round_robin(records)
    assert any("distinct teams" in v for v in violations)


def test_team_of_mapping_is_applied_before_counting():
    records = _make_valid_double_round_robin()
    # Canonicalise "Team 00" and an alias "Team ZERO" (never actually present here) to
    # prove the mapping function is actually consulted, not bypassed.
    violations = validate_double_round_robin(records, team_of=lambda name: name.upper())
    assert violations == []

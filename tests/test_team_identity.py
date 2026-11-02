import pytest

from matchweek_intelligence.team_identity import (
    UnmappedTeamNameError,
    canonical_team_name,
    known_raw_names,
)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("AFC Bournemouth", "Bournemouth"),
        ("Bournemouth", "Bournemouth"),
        ("Arsenal FC", "Arsenal"),
        ("Arsenal", "Arsenal"),
        ("Chelsea FC", "Chelsea"),
        ("Hull City AFC", "Hull City"),
        ("Sunderland AFC", "Sunderland"),
        ("Sunderland", "Sunderland"),
        ("Manchester United FC", "Manchester United"),
        ("Manchester United", "Manchester United"),
        ("Wolverhampton Wanderers FC", "Wolverhampton Wanderers"),
        ("Wolverhampton Wanderers", "Wolverhampton Wanderers"),
    ],
)
def test_canonical_team_name_resolves_known_variants(raw, expected):
    assert canonical_team_name(raw) == expected


def test_unmapped_name_raises_rather_than_being_guessed_at():
    with pytest.raises(UnmappedTeamNameError) as exc_info:
        canonical_team_name("Totally Unknown FC")
    assert exc_info.value.raw_name == "Totally Unknown FC"


def test_no_fuzzy_matching_a_near_miss_still_raises():
    # "Arsenal F.C." (with full stops) is not in the table and must not be guessed to
    # mean the same thing as "Arsenal FC" by any similarity heuristic.
    with pytest.raises(UnmappedTeamNameError):
        canonical_team_name("Arsenal F.C.")


def test_no_two_distinct_known_raw_names_collide_onto_a_wrong_shared_canonical_id():
    # Every raw name that differs only by an "FC"/"AFC" suffix convention must resolve
    # to the SAME real club, never two different ones sharing a name coincidentally.
    by_canonical: dict[str, set[str]] = {}
    for raw in known_raw_names():
        by_canonical.setdefault(canonical_team_name(raw), set()).add(raw)
    # Spot-check a few known multi-variant clubs actually collapsed as intended.
    assert by_canonical["Bournemouth"] == {"AFC Bournemouth", "Bournemouth"}
    assert by_canonical["Arsenal"] == {"Arsenal FC", "Arsenal"}


def test_known_raw_names_has_no_duplicates_and_covers_all_four_season_files():
    names = known_raw_names()
    assert len(names) == len(set(names))
    # 46 distinct raw strings were found by direct extraction across the four real
    # season files during the S02 audit (see team_identity.py's module docstring).
    assert len(names) == 46

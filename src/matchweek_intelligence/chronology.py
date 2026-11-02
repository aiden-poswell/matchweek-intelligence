"""Strict chronological cutoffs for as-of model inputs.

A current-season source can legitimately contain rows that are, relative to some
earlier simulated "as of" date, from the future. Any later modelling slice must never
fit on those rows. `as_of_filter` is the single choke point that enforces the DATE
cutoff: it excludes every record whose match_date is on or after the cutoff, and
batches same-day fixtures together (no partial-day leakage, since these sources carry
no kickoff-time guarantee reliable enough to order same-day fixtures within a day).

`as_of_filter` alone is NOT sufficient as a model-training input, and must not be
treated as one: a `result_missing` row (scheduled in the past, no score recorded —
see docs/DATA_CONTRACT.md) can still be strictly before the cutoff and would pass
`as_of_filter` unchanged, yet it carries no real outcome. `completed_training_results_as_of`
is the safer, model-facing helper: it additionally requires `status == "played_with_score"`,
so a later modelling slice that calls it can never accidentally train on a scoreless row
just because that row happens to be chronologically earlier than the cutoff.
"""

from __future__ import annotations

from datetime import date

from matchweek_intelligence.football_txt import MatchRecord


def as_of_filter(records: list[MatchRecord], cutoff_date: date) -> list[MatchRecord]:
    """Return only records strictly BEFORE cutoff_date (same-day fixtures excluded).

    Status-agnostic: this can still return `result_missing` rows. Model training code
    should use `completed_training_results_as_of` instead.
    """
    return [r for r in records if r.match_date < cutoff_date]


def completed_training_results_as_of(
    records: list[MatchRecord], cutoff_date: date
) -> list[MatchRecord]:
    """Return only ACTUALLY SCORED records strictly before cutoff_date.

    This is the helper any later modelling slice must use to build a training set: it
    requires both `match_date < cutoff_date` (same-day fixtures are always excluded,
    never partially included) AND `status == "played_with_score"` — a `result_missing`
    row never enters a training set, no matter how far in the past its date is.
    """
    return [r for r in records if r.match_date < cutoff_date and r.status == "played_with_score"]

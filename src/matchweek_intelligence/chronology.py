"""Strict chronological cutoffs for as-of model inputs.

A current-season source can legitimately contain rows that are, relative to some
earlier simulated "as of" date, from the future. Any later modelling slice must never
fit on those rows. `as_of_filter` is the single choke point that enforces this: it
excludes every record whose match_date is on or after the cutoff, and batches same-day
fixtures together (no partial-day leakage, since these sources carry no kickoff-time
guarantee reliable enough to order same-day fixtures within a day).
"""

from __future__ import annotations

from datetime import date

from matchweek_intelligence.football_txt import MatchRecord


def as_of_filter(records: list[MatchRecord], cutoff_date: date) -> list[MatchRecord]:
    """Return only records strictly BEFORE cutoff_date (same-day fixtures excluded)."""
    return [r for r in records if r.match_date < cutoff_date]

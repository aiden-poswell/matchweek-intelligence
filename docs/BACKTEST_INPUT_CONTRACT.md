# Backtest input contract

Status: this document defines the contract any future modelling slice (S03+) must satisfy to
read from this project's verified corpus. **No model is fitted anywhere in this repository as of
this slice.** This is a pre-registered design commitment, written before any model exists, so a
later slice can be checked against it rather than rationalising whatever it happens to produce.

## Row grain and canonical IDs

One row = one fixture. Grain: `(competition, season, match_date, home_team_raw, away_team_raw)`
at parse time (see `docs/DATA_CONTRACT.md`); a model-facing table must additionally carry
`home_team_id`/`away_team_id` resolved through `team_identity.canonical_team_name()` — never the
raw label directly, and never a fuzzy join. An unmapped name is a hard stop on building the
corpus (`UnmappedTeamNameError`), not a row to drop silently.

## Score integrity

Only rows with `status == "played_with_score"` may ever appear in a training or evaluation set.
A `result_missing` row is never treated as a 0-0, a bye, or an omission that can be safely
forward/back-filled. `corpus_validation.validate_scores()` must report zero violations
(non-negative scores; half-time never exceeds full-time) for any season before it is used.

## Eligibility by season

Only a season with `eligible_complete_season = true` in
`reports/s02_historical_corpus_quality.json` may be used as a COMPLETE historical season for
training or evaluation. As of this slice: **2023/24, 2024/25, 2025/26** are eligible; **2026/27
is not** (current, partial, and separately gated — see "Current vs. retrospective" below).
Eligibility is re-derived from the real corpus on every run, never cached as a static assumption
in modelling code.

## Chronological as-of cutoffs and same-day batching

A model may only be fit on `chronology.completed_training_results_as_of(records, cutoff_date)` —
never on `as_of_filter()` alone, which is status-agnostic and can still return a `result_missing`
row. Same-day fixtures are always included or excluded as a whole batch (`match_date <
cutoff_date`, strict): a model must never see one same-day fixture's result while being asked to
predict another same-day fixture, since this source carries no reliable kickoff-time field to
order within a day.

**A model may not:**
- Learn any same-day or future result relative to its own prediction cutoff.
- Use a season-end label (final table position, points total, goal difference for the season) as
  a predictor for any fixture within that same season — this is model-facing information
  leakage, not merely a chronology leakage, since the season-end label is only known once the
  season the model is predicting has already finished.
- Compute any feature from a full future season table, including a league-wide end-of-season
  ranking, even one computed from a DIFFERENT season than the one being predicted, if that other
  season's own matches are not all `match_date < cutoff_date` relative to the current prediction.

## First available training day and expanding training

The first fixture a model may ever predict is the earliest fixture, across all eligible seasons,
for which at least one prior eligible season (or a documented minimum number of prior
within-season matches — see "Minimum sample sizes" below) exists strictly before it. Training
is expanding, not a fixed rolling window, unless a later slice explicitly justifies and tests a
rolling alternative against the expanding baseline.

## Promoted-team cold-start policy

A club newly promoted into the eligible seasons (e.g. a club absent from an immediately prior
eligible season) must be assigned an explicit, documented cold-start prior (such as a
shrunk-toward-league-average strength) rather than silently inheriting any later top-flight
performance. A promoted club is never described as having "top-flight-only" history when a prior
lower-division record exists and is simply not ingested — state the limitation, do not imply
data that was not used.

## Supported competitions and seasons (frozen as of S02)

- **Competition:** English Premier League only.
- **Eligible historical seasons:** 2023/24, 2024/25, 2025/26 (380/380 scored each, verified).
- **Current, non-eligible season:** 2026/27 (50/380 scored as of 2026-11-02; blocked from any
  live/public claim per `docs/SOURCE_RIGHTS_AND_PROVENANCE.md`).
- No Championship, League One, League Two, or domestic cup competition is in scope.

## Minimum historical sample sizes for baseline comparison

A later slice's baseline comparison (league-wide 1X2 prior, rolling frequency, simple Poisson —
see `docs/FORECASTING_PROTOCOL.md`) must report the explicit N behind every evaluated metric and
must not report a calibration or reliability claim below a documented minimum N (suggested
floor: 100 held-out fixtures per evaluated bucket; a lower N must be reported as low-powered, not
suppressed or hidden). With three eligible seasons at 380 fixtures each, the maximum realistic
out-of-time evaluation set in the next slice is at most two seasons' worth of held-out fixtures
(~760), after reserving at least one season as the earliest training-only season.

## Current vs. retrospective — the line this project does not cross

Every model output this project ever produces from the current corpus is a **retrospective
simulation**: "what would a model fit only on data available before date X have said about
fixtures on or after date X." It is never presented as a live prediction about the actual
2026/27 season, because `live_claim_allowed` is hard-coded `False` in `build_data_quality.py` and
is not something any downstream code may override. A retrospective backtest over 2024/25 or
2025/26 fixtures is legitimate and useful; a current-week prediction advertised as live coverage
of 2026/27 is not something this corpus can honestly support yet.

## Quality gates before each training fold

Before fitting anything on a training fold, a later slice must re-verify, not assume:

1. The manifest hash check passes for every file the fold touches.
2. Every season in the fold has `eligible_complete_season = true` (for a season used in full) or
   is filtered through `completed_training_results_as_of()` with an explicit cutoff (for the
   current partial season, if ever used at all).
3. `season_structure.validate_double_round_robin()` returns zero violations for every complete
   season in the fold.
4. No team name in the fold is unmapped (`team_identity.canonical_team_name` resolves cleanly).

A fold failing any of these must stop before fitting, not fit anyway and note the caveat
afterwards.

## What this corpus cannot support

No expected goals (xG), no player-level data, no injuries, no formations, no bookmaker market
data, no tactical narrative. A model built from this corpus is a results-only statistical model;
any output describing WHY a team is favoured in football terms (press intensity, formation
mismatch, etc.) would be invented, not derived, and must not appear in any later slice's output.

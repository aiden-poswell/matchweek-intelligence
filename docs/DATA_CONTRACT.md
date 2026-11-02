# Data contract — updated in Slice 02

This describes all data this project currently ingests: four files from
`openfootball/england` at pinned commit `9ee7a0c351805c99cc334478a9bf04b7d0432fec` —
`2023-24/1-premierleague.txt`, `2024-25/1-premierleague.txt`, `2025-26/1-premierleague.txt`
(three complete historical seasons) and `2026-27/1-premierleague.txt` (current, partial
season). See `docs/SOURCE_RIGHTS_AND_PROVENANCE.md` and `reports/S02_FORMAT_AUDIT.md` for the
rights, freshness, and real-format audits behind this scope.

## Supported source sub-formats

Three real sub-formats are parsed, each independently validated against the real file before
any code was written (see `reports/S02_FORMAT_AUDIT.md`):

| Constant | Seasons | Header | Fixture separator | Scorer annotations |
| --- | --- | --- | --- | --- |
| `matchday_v_literal` | 2024/25, 2026/27 | `▪ Matchday N` | literal `" v "` | No |
| `matchday_score_between_no_v` | 2023/24 | `▪ Matchday N` | score sits between team names, no `" v "` | No |
| `regular_season_score_between_scorer_annotated` | 2025/26 | `▪ Regular Season - N` | score sits between team names, no `" v "` | Yes — consumed and discarded, see below |

Any OTHER sub-format is detected and **rejected** (`UnsupportedFootballTxtFormatError`), never
guessed at. `matchweek_intelligence.football_txt.detect_subformat()` is the single source of
truth for this classification, and `SUPPORTED_SUBFORMATS` is the single allowlist.

### Scorer-annotation lines (2025/26 only)

A scored fixture may be followed by one or more lines wrapped in parentheses, naming scorers and
minutes, which may themselves contain nested parentheses (e.g. `(p)` for penalty, `(og)` for own
goal) and may span more than one physical line (a block only ends once its parenthesis count
balances back to zero). These lines are consumed and discarded entirely before any fixture-line
parsing is attempted — they never contribute a fixture, a score, or any other feature, and a
scorer line's own digits can never override the fixture's displayed full-time score. An
unterminated scorer block (parentheses never balance before EOF or the next header/date line) is
quarantined as a real anomaly rather than silently absorbed.

## Match grain

`(competition, season, match_date, home_team_raw, away_team_raw)`.

This is **not** `(round, home, away)`. Direct inspection found round/matchday labels reused
across multiple real calendar dates for rearranged fixtures in **every one of the three
sub-formats** (e.g. "Matchday 29" three times in 2024/25; "Regular Season - 31" three times in
2025/26) — not a quirk of one format. The source-provided round label is carried through as
`raw_round_label`, an **untrusted, informational field only**, never used for identity or
ordering, and file order/round-number monotonicity is never assumed either (see
`tests/test_football_txt.py` for an out-of-order synthetic proof).

This composite key is also not guaranteed unique in general; `build_data_quality.py` and the
Stage C corpus builder both check for and report any duplicate grain key rather than assuming
uniqueness.

## Canonical team identity

Team-name spelling is **not consistent across seasons** — direct extraction of every raw label
in all four files found 46 distinct raw strings for 27 real clubs. Concretely: 2023/24, 2024/25
and 2026/27 suffix every club with "FC"/"AFC" (except "AFC Bournemouth", where AFC is a genuine
name prefix); 2025/26 drops the suffix for every club EXCEPT Chelsea, which it still prints as
"Chelsea FC" throughout — a genuine source inconsistency, not a transcription error here.

`matchweek_intelligence.team_identity.canonical_team_name(raw_name)` is a hand-reviewed,
evidence-built lookup table (never a suffix-stripping regex, never a fuzzy/similarity join). Any
raw name not in the table raises `UnmappedTeamNameError`, which is a **hard stop** on building
the historical corpus — never silently guessed at or ignored.

## Fields

| Field | Type | Notes |
| --- | --- | --- |
| `competition` | str | Fixed `"premier-league"`. |
| `season` | str | `"2023-24"`, `"2024-25"`, `"2025-26"`, or `"2026-27"`. |
| `match_date` | ISO date | Actual real calendar date the fixture is/was scheduled for. Year is inferred from the file's own `# Date(s) <start> - <end>` header when a date line omits it, re-anchored at an explicit year if the source states one (true for 2024/25, 2025/26, 2026/27 at the real Dec->Jan boundary) or, failing that, inferred purely from the month sequence decreasing (2023/24 never restates the year at all — see `football_txt._YearTracker`). |
| `raw_round_label` | str | Verbatim source section header text. Informational only — not unique, not an ordering key. |
| `home_team_raw`, `away_team_raw` | str | Verbatim source team label. Pass through `team_identity.canonical_team_name()` before any cross-season comparison. |
| `home_score`, `away_score` | int or null | Full-time score. **Null means "no score recorded," never "0-0."** |
| `home_score_ht`, `away_score_ht` | int or null | Half-time score, when the source prints one. Observed absent on some scored fixtures — null in that case, never assumed equal to full-time. |
| `status` | enum | See below. |
| `source_line_no` | int | 1-indexed line number in the raw file. |

## Status semantics

Unchanged from S01: `played_with_score` (a score is present), `result_missing` (no score,
`match_date < as_of_date` — may mean the source simply hasn't caught up, or a genuine
postponement; this source has no explicit postponement marker, so the two cannot currently be
told apart, which is stated as a limitation, not resolved by assumption), and
`scheduled_future` (no score, `match_date >= as_of_date`).

## As-of chronological discipline

Two helpers, with deliberately different contracts:

- `chronology.as_of_filter(records, cutoff_date)` — keeps only `match_date < cutoff_date` rows.
  Status-agnostic: **can still return `result_missing` rows.**
- `chronology.completed_training_results_as_of(records, cutoff_date)` — the safer, model-facing
  helper. Requires BOTH `match_date < cutoff_date` AND `status == "played_with_score"`. Any later
  modelling slice must build its training set from this helper, not from `as_of_filter` alone —
  a `result_missing` row must never enter a training set merely because its date is in the past.

Same-day fixtures are always excluded or included as a whole batch from either helper, never
partially — there is no reliable kickoff-time field in this source.

## Freshness and completeness fields (`reports/s01_data_quality.json`)

S01's single `current_season_publishable` field was removed after an independent reviewer
reproduced a real defect: on a synthetic current season with 1 scored + 2 past-unscored fixtures
dated less than 14 days ago, that field returned `True` — "recent missing outcomes are still
missing outcomes." It is replaced by three deliberately separated fields:

- **`historical_season_complete`** (bool): True only when the season has exactly 380 fixtures,
  every one is scored, `season_structure.validate_double_round_robin` finds zero violations,
  there is zero quarantine/duplication/team-identity error, AND `season_end_date < as_of_date`.
  A season in progress can never satisfy this.
- **`current_results_coverage_sufficient`** (bool): True only when there is no evidenced
  missing-result gap (`result_missing_count == 0`) and the full fixture list is structurally
  clean. This deliberately does **not** mean "the season is complete" — a season with nothing
  played yet trivially satisfies it; it means "no gap has been found," not "there's enough data
  to model."
- **`live_claim_allowed`** (bool): hard-coded `False`, unconditionally, in
  `build_data_quality.py`. Per-file "is this still being actively updated" provenance requires an
  external GitHub commit-history check (done by hand for 2026/27 in
  `docs/SOURCE_RIGHTS_AND_PROVENANCE.md` §1d — last real update found: 2026-09-21), which is not
  derivable from file bytes alone. `source_recency` records this honestly as
  `not_independently_verified_by_automated_pipeline` rather than defaulting to true. A frozen
  pinned-commit snapshot must never become "live" just because every match in it was scored by
  some earlier as-of date.

Also present per file: `fixture_count`, `scored_count`, `result_missing_count`,
`scheduled_future_count`, `season_start_date`/`season_end_date`, `earliest_scored_date`,
`latest_scored_date`, `earliest_scheduled_future_date`, `result_missing_dates`,
`stale_result_missing_count`/`stale_result_missing_dates` (kept as a diagnostic — staleness is
informative but, per the fixed defect above, "not stale" never implies "complete"),
`duplicate_grain_keys`, `team_identity_errors`, `round_robin_violations`,
`quarantined_line_count`/`quarantined_lines`.

## Season structural validation

`matchweek_intelligence.season_structure.validate_double_round_robin(records, team_of=...)`
checks the full 20-team double round-robin shape: exactly 380 fixtures, exactly 20 distinct
canonical teams, exactly 19 home + 19 away fixtures per team, and exactly one home-and-away
pairing per opponent pair. This catches a missing, duplicated, or reversed (home/away swapped)
fixture even when the total count happens to still be 380 — a header that says "380" is never
treated as an actual row-count check.

## Integrity

`reports/s01_source_manifest.json` records the pinned commit and, per file, path/SHA-256/byte
count for all four now-fetched files. The two S01 hashes
(`2024-25/1-premierleague.txt`, `2026-27/1-premierleague.txt`) are byte-identical to S01's
original manifest — confirmed directly, never silently replaced. `build_data_quality.py`
re-hashes every on-disk raw file against the manifest before parsing it and fails closed
(`DataQualityError`) on any mismatch or missing file.

## What this contract does not cover

No venue, attendance, referee, or competition-stage data. No kickoff-time-based same-day
ordering. No coverage of Championship/League One/Two or any non-Premier-League competition, even
though some of those files exist in the same repository. No postponement/abandonment marker in
the source (so `result_missing` cannot currently be split into "feed lag" vs. "genuinely
postponed").

# Data contract — Slice 01

This describes the only data this project currently ingests: two files from
`openfootball/england` at pinned commit `9ee7a0c351805c99cc334478a9bf04b7d0432fec` —
`2024-25/1-premierleague.txt` (complete historical season) and `2026-27/1-premierleague.txt`
(current, partial season). See `docs/SOURCE_RIGHTS_AND_PROVENANCE.md` for the rights and
freshness audit behind this scope decision.

## Supported source sub-format

Only the `matchday_v_literal` Football.TXT sub-format is parsed (`▪ Matchday N` section headers;
fixture lines of the form `[HH:MM] <home> v <away> [<hs>-<as> (<hts>-<ats>)]`). Two other real
sub-formats exist in the same upstream repository (`regular_season_scorer_annotated` for 2025/26,
`matchday_no_v_literal` for 2023/24) and are explicitly detected and **rejected**, never guessed
at. `matchweek_intelligence.football_txt.detect_subformat()` is the single source of truth for
this classification.

## Match grain

`(competition, season, match_date, home_team_raw, away_team_raw)`.

This is **not** `(round, home, away)`. Direct inspection of the real source found round/matchday
labels reused across multiple real calendar dates for rearranged fixtures (e.g. "Matchday 29"
appearing three times in the 2024/25 file). The source-provided round label is carried through as
`raw_round_label` — an **untrusted, informational field only**, never used for identity or
ordering.

This composite key is also not guaranteed unique in general (two fixtures between the same pair
on the same date would collide), though no such collision was observed in either ingested file —
`build_data_quality.py` checks for and reports any duplicate grain key rather than assuming
uniqueness.

## Fields

| Field | Type | Notes |
| --- | --- | --- |
| `competition` | str | Fixed `"premier-league"` for this slice's two files. |
| `season` | str | `"2024-25"` or `"2026-27"`. |
| `match_date` | ISO date | Actual real calendar date the fixture is/was scheduled for. Year is inferred from the file's own `# Date <start> - <end>` header when a date line omits it (every line after the first); see `football_txt.py` for the rollover rule at the season's calendar-year boundary. |
| `raw_round_label` | str | Verbatim source section header text (e.g. `"Matchday 29"`). Informational only — not unique, not an ordering key. |
| `home_team_raw`, `away_team_raw` | str | Verbatim source team label, including or excluding "FC"/"AFC" suffixes exactly as the source prints them. No canonical team-identity crosswalk is built in this slice. |
| `home_score`, `away_score` | int or null | Full-time score. **Null means "no score recorded," never "0-0."** |
| `home_score_ht`, `away_score_ht` | int or null | Half-time score, when the source prints one. Observed to be sometimes absent even on a scored fixture (e.g. a scoreline printed as bare `0-0` with no half-time parenthetical) — null in that case, not assumed equal to the full-time score. |
| `status` | enum | See below. |
| `source_line_no` | int | 1-indexed line number in the raw file, for traceability back to `quarantined_lines`/debugging. |

## Status semantics

Three statuses are distinguished, derived strictly from (a) whether a score is present and (b)
how `match_date` compares to a caller-supplied `as_of_date` — **never from `match_date` alone**:

- `played_with_score` — a score is present. The only status that counts as a completed result.
- `result_missing` — no score, and `match_date < as_of_date`. The fixture was scheduled in the
  past but the source has not recorded an outcome. **This does not mean the match was not
  played** — it may have been played and the feed simply hasn't caught up (the confirmed case
  here), or postponed, or genuinely unplayed. The two real files inspected for this slice contain
  no explicit postponement marker text, so this project cannot currently disambiguate "feed
  lag" from "actually postponed" from source content alone — stated as an honest limitation
  rather than invented as false precision. `build_data_quality.py` additionally flags any
  `result_missing` row older than `STALE_RESULT_MISSING_DAYS` (14, see §1e of the rights doc) as
  `stale_result_missing`, which is what drives `current_season_publishable = False`.
- `scheduled_future` — no score, and `match_date >= as_of_date`. A fixture that has not yet
  happened as of the given as-of date. Never treated as missing data.

A fixture scheduled in the past without a score is never silently turned into a 0-0 draw and
never marked "played" by date alone — both are enforced by construction (the score fields are
only ever populated from an actual parsed `\d+-\d+` token).

## As-of chronological discipline

`matchweek_intelligence.chronology.as_of_filter(records, cutoff_date)` is the single choke point
any later modelling slice must use to exclude future information: it keeps only records with
`match_date < cutoff_date`, so same-day fixtures are always excluded or included as a whole batch,
never partially — there is no reliable kickoff-time field in this source to order within a day.
Tests in `tests/test_chronology.py` prove this with synthetic fixtures spanning a cutoff.

## Freshness fields (`reports/s01_data_quality.json`)

Per file: `fixture_count`, `scored_count`, `result_missing_count`, `scheduled_future_count`,
`earliest_scored_date`, `latest_scored_date`, `earliest_scheduled_future_date`,
`result_missing_dates` (full list), `stale_result_missing_count`/`stale_result_missing_dates`,
`duplicate_grain_keys`, `quarantined_line_count`/`quarantined_lines`, and the boolean
`current_season_publishable`. Note this last flag is a staleness gate, not literally
"is this a current season" — it is (vacuously, correctly) `true` for the complete 2024/25 file,
because a file with zero `result_missing` rows has zero stale ones by construction.

## Integrity

`reports/s01_source_manifest.json` records the pinned commit, each fetched file's path,
SHA-256, and byte count. `build_data_quality.py` re-hashes the on-disk raw file against the
manifest before parsing it and fails closed (`DataQualityError`) on any mismatch or missing file
— this is a tamper/corruption check, not a network refetch.

## What this contract does not cover

No venue, attendance, referee, scorer, or competition-stage data (not present in the supported
sub-format). No canonical team-ID crosswalk (raw labels only). No kickoff-time-based same-day
ordering. No coverage of Championship/League One/Two or any non-Premier-League competition in
this slice, even though some of those files exist in the same repository.

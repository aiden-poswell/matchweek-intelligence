# S02 historical corpus audit

Machine-readable form: `reports/s02_historical_corpus_quality.json`, produced by
`matchweek_intelligence.build_historical_corpus.build_report()` against the real pinned-commit
cache, manifest-verified before any report is written. All figures below were read directly from
that generated file, not hand-counted.

**Note on `as_of_date`:** this report uses a fixed analytical constant, `2027-01-01`, chosen only
to be safely past every historical season's own end date — it is NOT "today" and is unrelated to
the live freshness check in `reports/s01_data_quality.json`, which uses the real current date
(2026-11-02) and remains the authoritative "as of now" view for the current 2026/27 season.
Evaluating 2026/27 against this report's fixed constant produces different
scored/missing/future counts than the S01 freshness report — both are correct for what they
each measure; neither supersedes the other.

## Result: all three historical candidate seasons are eligible

| Season | Eligible | Fixtures | Scored | H / D / A | Round-robin violations | Date window |
| --- | --- | --- | --- | --- | --- | --- |
| 2023/24 | **True** | 380 | 380/380 | 175 / 82 / 123 | 0 | 2023-08-11 → 2024-05-19 |
| 2024/25 | **True** | 380 | 380/380 | 155 / 93 / 132 | 0 | 2024-08-16 → 2025-05-25 |
| 2025/26 | **True** | 380 | 380/380 | 162 / 104 / 114 | 0 | 2025-08-15 → 2026-05-24 |
| 2026/27 | False (current, not a historical candidate) | 380 | 50/380 | 18 / 16 / 16 (scored so far) | 0 | 2026-08-21 → 2027-05-30 |

Zero duplicate match-grain keys, zero quarantined lines, zero team-identity errors, zero score
or half-time integrity violations, zero date-window violations in any of the four files. H+D+A
sums to exactly 380 for each of the three complete seasons, independently confirming the scored
count.

## What "eligible" required, and what was actually checked (not assumed)

1. **Exact fixture count and scoring.** 380 unique fixtures, 380 scored, 0 result-missing — read
   from the actual parsed row count, never from the source header's own "# Matches 380" line
   (which is present in all four files but was independently verified against the real parsed
   total rather than trusted).
2. **Full double round-robin pairing matrix** (`season_structure.validate_double_round_robin`):
   exactly 20 canonical teams, 19 home + 19 away fixtures per team, exactly one home-and-away
   fixture per opponent pair. This is a stronger check than a duplicate-key or total-count check
   alone — it would catch a reversed (home/away swapped) fixture even if the total remained 380
   and no (date, home, away) key repeated. All three historical seasons passed with zero
   violations.
3. **Score integrity** (`corpus_validation.validate_scores`): no negative score (structurally
   impossible given the parser's own `\d+-\d+` regex, but asserted explicitly as a second line of
   defence) and no half-time score exceeding its own full-time score. Zero violations.
4. **Calendar-window integrity** (`corpus_validation.validate_date_window`): every match date
   falls inside the season's own declared `# Date(s) <start> - <end>` span. Zero violations.
5. **Canonical team identity.** All 46 distinct raw team-name strings across the four files
   resolved against the hand-reviewed table in `team_identity.py` with zero unmapped names and
   zero collisions. See `reports/S02_FORMAT_AUDIT.md` for the real naming inconsistencies this
   table was built to handle (suffix variation, and the Chelsea-only within-file exception in
   2025/26).

No STOP condition (per the brief's hard-stop list) was triggered: no season failed to reconcile
to the 20-team/380-match double round-robin, no raw text was ambiguous, no team mapping
collided, no source hash drifted, and the source is verifiably the CC0 repository at the pinned
commit throughout.

## Aggregate totals only — no raw match table in the review export

Per the brief, this audit and its exports report bounded aggregate counts (fixture totals,
H/D/A splits, date spans, violation counts) and sanitised source metadata only. No full
player/club-level raw match table is included in `reports/s02_historical_corpus_quality.json` or
in the review ZIP — the real per-fixture rows live only in the gitignored `data/raw/` cache,
which the licence permits locally but which this project keeps out of every tracked/exported
artifact to keep the review snapshot small and hygiene-clean.

## Source integrity re-confirmed before this report was written

`build_historical_corpus.build_report()` re-hashes every on-disk raw file against
`reports/s01_source_manifest.json` before parsing anything, and raises `HistoricalCorpusError`
(no report is written) on any mismatch. The two files inherited from S01
(`2024-25/1-premierleague.txt`, `2026-27/1-premierleague.txt`) carry byte-identical SHA-256
hashes to S01's original manifest — confirmed directly, not merely asserted:

| Path | SHA-256 | Unchanged since S01? |
| --- | --- | --- |
| `2023-24/1-premierleague.txt` | `0bfb4a7fffe0b1bf7318955686eafeb28fc9676346ae433259e7409d69551450` | new in S02 |
| `2024-25/1-premierleague.txt` | `e39716b01af0c8654a9fae7b5555e6b02f506ea05239e0d0eef41936ba80e1e3` | **yes, identical** |
| `2025-26/1-premierleague.txt` | `38c1de56c9e9b6662c7efc1420b7e1fe00dddbb502fe72d8f759e773ba3c093b` | new in S02 |
| `2026-27/1-premierleague.txt` | `a2366ea9f7f55b8afd666e455666ba9019f9c62da8864f6bcf3adff65300b445` | **yes, identical** |

## Unresolved / out of scope for S02

- Championship, League One, League Two and both domestic cup competitions exist in the same
  repository and are not ingested — Premier League only, per the forecasting protocol's "a
  selected league" scope.
- The source still carries no explicit postponement marker; a `result_missing` row (there are
  none in the three eligible historical seasons, by definition of eligibility) still cannot be
  told apart from a genuine postponement versus a feed-lag gap purely from file content.
- No model is fitted anywhere in this slice. S03 is the first slice permitted to fit anything,
  and only against `chronology.completed_training_results_as_of()` output, per
  `docs/BACKTEST_INPUT_CONTRACT.md`.

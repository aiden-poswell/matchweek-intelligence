# S02 format audit — 2023/24 and 2025/26 Football.TXT, real-file inspection

All excerpts below are short, attributed quotations from `openfootball/england` at pinned
commit `9ee7a0c351805c99cc334478a9bf04b7d0432fec`, fetched via the project's own
`matchweek_intelligence.fetch` and verified against `reports/s01_source_manifest.json` before
any code was written against them. No full source file is copied into this report or into Git.

## 2023-24/1-premierleague.txt — `matchday_score_between_no_v`

- **Header style:** `▪ Matchday N` (same literal bullet/label style as 2024/25 and 2026/27).
- **Fixture line, no literal `" v "`:**
  ```
  20:00  Burnley FC               0-3 (0-2)  Manchester City FC
  ```
  Score sits directly between the two team names; home/away must be split on the score token's
  position, not on any separator word.
- **Continuation fixtures (same kickoff time, time omitted on the line):**
  ```
  15:00  AFC Bournemouth          1-1 (0-0)  West Ham United FC
         Brighton & Hove Albion FC  4-1 (1-0)  Luton Town FC
  ```
- **Half-time scores:** present on every single one of 380 fixtures in this file — no bare
  full-time-only row was found (`grep` for a trailing score with no following `(...)` across the
  whole file returned zero matches).
- **Year rollover — the critical real finding:** this file **never states an explicit year**,
  not even at the Dec->Jan boundary:
  ```
  Tue Dec 26
  ...
  Sun Dec 31
  Mon Jan 1
  Tue Jan 2
  ```
  Every other file this project ingests restates the year explicitly at the first January date
  line. 2023/24 does not. Its year must be inferred purely from the month sequence decreasing
  (Dec, 12 -> Jan, 1), bounded by the season-span header's declared end year. This is the one
  real case that exercises the "no explicit year at rollover" branch of
  `football_txt._YearTracker` with real data, not just a synthetic test.
- **Postponed-round handling:** round labels repeat out of file order exactly as in the other
  three files — e.g. `Matchday 34`, `Matchday 29`, `Matchday 26`, `Matchday 2`, `Matchday 18`,
  `Matchday 17` each appear twice in this file (`grep -c` count), confirming rearranged fixtures
  are not unique to one sub-format.
- **Anomalous lines:** none found. The real file parses to exactly 380 records, 0 quarantined
  lines, 0 round-robin violations (verified in this session against the actual fetched file).

## 2025-26/1-premierleague.txt — `regular_season_score_between_scorer_annotated`

- **Header style:** `▪ Regular Season - N` (not `Matchday`) — the only one of the four files
  using this label.
- **Fixture line, score between team names (same shape as 2023/24, no literal `" v "`):**
  ```
  19:00   Liverpool  4-2 (1-0)  Bournemouth
  ```
- **Scorer-annotation continuation, single line, nested parentheses (penalty marker):**
  ```
                    (Matt ORILEY 55'(p); RODRIGO MUNIZ 90+7')
  ```
- **Scorer-annotation continuation, genuinely spanning two physical lines:**
  ```
                    (Hugo EKITIKE 37', Cody GAKPO 49', Federico Chiesa 88', MOHAMED SALAH 90+4';
                     Antoine SEMENYO 64', 76')
  ```
  The first physical line ends with an unbalanced open paren (net `+1`); the second line closes
  it (net `-1`), bringing the running balance back to zero — this is the real shape the
  balance-tracking consumer in `football_txt._parse_score_between` was built and tested against,
  not a hypothetical.
- **Scorer lines never contain a score-shaped token.** A direct search of every continuation
  line (10+ leading spaces, non-fixture) for a `\d+-\d+` pattern across the whole file returned
  zero matches — minute markers use `'` (apostrophe), never a dash, so there is no real
  ambiguity between a scorer annotation and an actual score in this file. The parser still
  defends against this structurally (scorer blocks are fully consumed before any score-pattern
  search is attempted on a line), rather than relying on this absence continuing to hold.
- **A genuine within-file team-name inconsistency:** every club in this file drops the "FC"
  suffix (`Arsenal`, `Liverpool`, `Manchester City`, ...) **except Chelsea**, which is printed
  `Chelsea FC` in all 38 of its appearances (0 occurrences of a bare `Chelsea` — checked
  directly, not assumed). Recorded in `team_identity.py`'s mapping table and its module
  docstring.
- **Year rollover:** this file DOES restate the year explicitly at the boundary —
  `Thu Jan 1 2026` — same convention as 2024/25 and 2026/27, unlike 2023/24.
- **Postponed-round handling:** `Regular Season - 31` appears three times at different points
  in file order (lines ~748, ~866, ~1038 in the raw file), confirming the same rearranged-fixture
  pattern found in every other sub-format.
- **Anomalous lines:** none found. The real file parses to exactly 380 records, 0 quarantined
  lines, 0 round-robin violations (verified in this session against the actual fetched file).

## Cross-format findings that generalise

- Round-label reuse/out-of-order reprinting is present in **all four** files, across **all
  three** sub-formats — never assume round numbers are unique or monotonic with file order, in
  any of them.
- Team-name spelling is inconsistent **both across and within** files (the Chelsea case above is
  a within-file inconsistency, not merely a cross-season one) — never fuzzy-match; use the
  reviewed `team_identity` table or fail closed.
- Year inference cannot assume a uniform convention: three of the four files restate the year
  explicitly at the calendar-year boundary; one (2023/24) never does and must be inferred from
  month-sequence direction alone, bounded by the season-span header.

## What this audit does NOT claim

No statement here is based on a README example or a header's claimed match count alone — every
fixture/record/violation count quoted was produced by actually running
`matchweek_intelligence.football_txt.parse_football_txt` and
`matchweek_intelligence.season_structure.validate_double_round_robin` against the real fetched
file content in this session (see `reports/s02_historical_corpus_quality.json` and
`reports/S02_HISTORICAL_CORPUS_AUDIT.md` for the full per-season results).

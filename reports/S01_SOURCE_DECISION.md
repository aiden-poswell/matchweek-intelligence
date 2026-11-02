# S01 source decision — go/no-go

Full detail and evidence: `docs/SOURCE_RIGHTS_AND_PROVENANCE.md`. This memo states the decision
plainly.

## Decision

**ACCEPT** `openfootball/england` (pinned commit `9ee7a0c351805c99cc334478a9bf04b7d0432fec`) as
the project's data source, with two explicit conditions:

1. **Current-season (2026/27) status is BLOCKED for any public/live claim.** The file's own
   per-path commit history shows its last real content update was 2026-09-21, six weeks before
   this audit (2026-11-02). `reports/s01_data_quality.json` (produced by the real
   `build_data_quality` CLI, not hand-counted) shows 39 of 380 fixtures are missing scores for
   scheduled-past matches, 19 of which (all of Matchday 6, most of Matchday 7 — Oct 10/11/12 and
   17/18) exceed the 14-day bound adopted after inspecting the real season schedule. This is a
   genuine feed gap, independently confirmed via the file's own commit history, not inferred from
   the repository's overall `pushed_at` timestamp.
2. **Only the `Matchday N` / literal-`v` fixture sub-format is parsed in this slice.** Direct
   inspection found the same nominal file (`1-premierleague.txt`) uses three different real
   sub-formats across 2023/24, 2024/25, 2025/26 and 2026/27. 2024/25 and 2026/27 share the
   supported sub-format; 2023/24 and 2025/26 use different ones and are detected-but-rejected by
   the parser rather than guessed at.

**REJECT** `footballcsv/england` — no 2021/22 or later data exists; repository inactive since
2023-05.

**REJECT** `openfootball/football.json` for this slice — a mirror of the primary source, lags it
by at least a day, adds no independent corroboration.

**REJECT (public use)** `oladeeayo/open-matchday` — no licence file exists at all; its own
`DISCLAIMER.md` restricts use to personal/non-commercial and names upstream providers (incl.
Wikipedia/Wikidata under CC BY-SA) whose terms this project has not undertaken to meet.
Permitted only as a private, non-ingested, non-redistributed freshness cross-check — not used
anywhere in this slice's code, data, or exports.

## What this unlocks for Slice 02+

- A historical backtest built on 2024/25 (complete, 380/380 scored, schema-verified).
- A legitimate, honestly-reported "why we are not claiming live 2026/27 coverage" finding —
  itself a useful, interview-defensible result, not a failure to hide.
- A documented reason 2025/26 is not yet ingested (different schema sub-format) rather than a
  silent gap.

## What remains blocked

- No current-matchweek forecast, no live dashboard, no public claim about 2026/27 form, until a
  source passes the freshness gate on its own terms (not by switching to a worse-rights source).

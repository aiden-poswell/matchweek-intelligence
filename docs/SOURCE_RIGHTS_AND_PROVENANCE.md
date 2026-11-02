# Source rights and provenance — Matchweek Intelligence, Slice 01

All findings below were produced by directly querying the GitHub API (`gh api`) against the
live repositories on 2026-11-02, not by recalling prior knowledge of these projects. Raw
responses are not reproduced verbatim here where long, but every fact stated is attributable to
a specific API call made during this audit.

## 1. Primary source — `openfootball/england`

- **Repository:** <https://github.com/openfootball/england>
- **Pinned commit (master, as of 2026-11-02):** `9ee7a0c351805c99cc334478a9bf04b7d0432fec`
  (commit date 2026-10-15T14:42:31Z, message: "EFL Cup 2020-21: Leyton Orient v Tottenham
  Hotspur forfeited (#63)" — i.e. the most recent repo-wide commit was a *historical correction*
  to a 2020/21 cup fixture, not an update to the current season).
- **Licence:** `LICENSE.md` at repo root is the full, unmodified **CC0 1.0 Universal** legal
  text (verified by reading the actual file content, not just GitHub's detected SPDX tag).
  `README.md` states explicitly: *"The football.db schema, data and scripts are dedicated to the
  public domain. Use as you please with no restrictions whatsoever."* This is a clean,
  explicit data-level grant — not a licence scoped to "software" that is merely silent on the
  data files — the publisher's own words explicitly cover **data**, not just code.
- **Residual provenance risk (documented, not dismissed):** a CC0 declaration by the repository's
  maintainer is evidence the maintainer intends to place their own compiled work in the public
  domain. It is not independent proof that every underlying fact (a score, a kickoff time) was
  itself free of any third party's rights before the maintainer recorded it. Match results and
  fixture lists are generally treated as facts rather than copyrightable expression in most
  jurisdictions, and the UK/EU database right attaches to the compiler of a database, not to the
  underlying facts — so the maintainer compiling publicly-reported results into this dataset and
  releasing their compilation as CC0 is a reasonable and commonly-accepted basis for reuse, but it
  is not a watertight guarantee against every conceivable claim. This residual risk is judged
  **low** given the data is limited to scores/dates/team names (no copyrighted text, no images,
  no proprietary tracking metrics), but it is recorded here rather than silently assumed away.
- **Permission scope:** reproduction, redistribution, derived figures, and a public website are
  all within the CC0 grant as written. No separate "research only" or "non-commercial" carve-out
  exists in this repository, unlike the `oladeeayo/open-matchday` candidate below.

### 1a. Season file availability (verified by direct fetch, not README example)

| Season | File(s) present | Fetched & inspected |
| --- | --- | --- |
| 2023/24 | `1-premierleague.txt` | Yes |
| 2024/25 | `1-premierleague.txt` (+ other divisions, `eflcup.txt`, `facup.txt`) | Yes |
| 2025/26 | `1-premierleague.txt`, `1-premierleague-full.txt` (+ other divisions) | Yes |
| 2026/27 | `1-premierleague.txt`, `2-championship.txt` only | Yes |

### 1b. Critical finding — the Football.TXT schema is NOT stable across seasons

Directly inspecting file content (not assuming uniformity) found **three distinct sub-formats**
for what is nominally the same `1-premierleague.txt` file, across four consecutive seasons of the
same competition in the same repository:

| Season | Section header | Fixture line style | Scorer detail lines |
| --- | --- | --- | --- |
| 2023/24 | `▪ Matchday N` | `home  score (HT)  away` (no literal `v`) | No |
| 2024/25 | `▪ Matchday N` | `home  v  away  score (HT)` (literal `v`) | No |
| 2025/26 | `▪ Regular Season - N` | `home  score (HT)  away` (no literal `v`) | **Yes** (goal minutes, own-goals, penalties) |
| 2026/27 (partial) | `▪ Matchday N` | `home  v  away  [score (HT)]` (literal `v`) | No |

This is a genuine, material finding, not a guess: the upstream generator/export tooling changed
format at least twice within five seasons. **Slice 01's parser (Stage B) targets only the
`Matchday` + literal-`v` sub-format** shared by 2024/25 and 2026/27, because those are the two
files the project actually needs (one complete historical season, one partial current season for
the freshness gate). 2023/24 and 2025/26 use different sub-formats and are **detected but not
parsed** in this slice — see `docs/DATA_CONTRACT.md` and `reports/s01_data_quality.json`. This is
a deliberate scope decision, not an oversight: guessing a shared parser across three different
real formats without separately validating each would be exactly the "guessy parser" the brief
asked us not to build.

### 1c. Critical finding — round/matchday numbers are not unique keys

Directly grepping the fetched files found that a single round label (e.g. "Matchday 29" in
2024/25, "Regular Season - 31" in 2025/26) appears **more than once**, at different points in the
file, because a fixture originally scheduled for that round was rearranged/postponed and actually
played on a different real calendar date — interleaved with a *later* round's fixtures in file
order. Examples directly observed:
- 2024/25: `Matchday 29` appears 3 times; `Matchday 15` appears 2 times.
- 2025/26: `Regular Season - 31` appears 3 times, with the Wolves v Arsenal fixture from that
  round appearing on "Wed Feb 18" — printed *between* Regular Season 26 and Regular Season 27 in
  file order, confirming a genuine rearrangement, not a formatting artefact.

This directly confirms the brief's warning and settles the grain design question: the match grain
used in this project is **(competition, season, actual_match_date, home_team_label,
away_team_label)**, never `(round, home, away)`. The source-provided round/matchday label is
carried through as an untrusted, informational field only — see `docs/DATA_CONTRACT.md`.

### 1d. Freshness finding — the 2026/27 file is stale, independently confirmed

Per-matchday scoring coverage in `2026-27/1-premierleague.txt`, counted directly from the fetched
file content:

| Matchday | Scheduled date | Fixtures scored |
| --- | --- | --- |
| 1–5 | Aug 21 – Sep 20, 2026 | 10/10 each (50/50 total) |
| 6 | Oct 10, 2026 | 0/10 |
| 7 | Oct 17, 2026 | 0/10 |
| 8 | Oct 23, 2026 | 0/10 |
| 9 | Oct 31, 2026 | 0/10 |
| 10–38 | Nov 7, 2026 – May 30, 2027 | 0/10 each (genuinely future — not stale) |

Per-file commit history (`gh api 'repos/openfootball/england/commits?path=2026-27/1-premierleague.txt'`)
shows the last real content change to this specific file was **2026-09-21T10:35:47Z**
("auto-update week 39") — six weeks before this audit's as-of date of 2026-11-02, despite the
overall repository showing commit activity as recently as 2026-10-15 (to unrelated historical
files). **A repository-level `pushed_at` timestamp does not establish that any specific file's
scores are current** — this is exactly the trap the brief warned against, and it is independently
confirmed here by checking the file's own commit history, not the repo's.

As of 2026-11-02 (Australia/Sydney, UTC+11), Matchday 6 (scheduled Oct 10) is **23 days** past its
scheduled date with no recorded score; Matchday 9 (Oct 31) is **2 days** past. These figures (and
every count in this section) are taken directly from `reports/s01_data_quality.json`, produced by
`uv run python -m matchweek_intelligence.build_data_quality` against the real fetched file with
`as_of_date=2026-11-02` — not hand-counted. The actual, code-verified breakdown:

- **39 fixtures** (of 380) are `result_missing` (scheduled in the past, no score recorded):
  2026-10-10/11/12 (Matchday 6), 10-17/18/19 (Matchday 7), 10-23/24/25 (Matchday 8), 10-31
  (Matchday 9), and 11-01.
- Of those, **19 fixtures** exceed the 14-day staleness bound (§1e) as of 2026-11-02:
  2026-10-10/11/12 and 10-17/18 — i.e. all of Matchday 6 and most of Matchday 7. The 10-19 fixture
  is exactly 14 days stale (not `> 14`) and so is correctly not flagged by the strict bound, and
  Matchday 8 (10–12 days stale) and Matchday 9/11-01 (2/1 days stale) are correctly not flagged
  either — they are missing, honestly reported as `result_missing`, but not yet over the bound.
- `current_season_publishable` for this file: **False** (19 > 0 stale missing results is enough to
  fail closed; the gate does not require every missing result to be stale).

This preliminary web review finding is **confirmed, with exact figures**, not merely repeated.

### 1e. Why 14 days is a reasonable bound here, not an arbitrary import

Premier League matchdays in this source are scheduled roughly weekly, with occasional 2–3 week
gaps around FIFA international windows (the Sep 20 → Oct 10 gap above is exactly such a window,
visible in the schedule itself, not a data problem). A single missed result during an
international break is expected and not evidence of staleness by itself. But this source's own
`auto-update` commit cadence (weekly, by its own commit messages) means a genuinely live feed
should show a result within days of a match being played, not weeks. 14 days comfortably covers
the longest normal scheduling gap in this competition while still catching a feed that has
genuinely stopped updating, which is what Matchdays 6–8 show.

### 1f. `current_season_publishable` status

**BLOCKED.** The 2026/27 file fails closed: 19 scheduled-past fixtures (Matchday 6 in full, most
of Matchday 7) are missing scores beyond the 14-day bound, and this is a structural feed gap, not
an ambiguous edge case — confirmed by the actual `build_data_quality` output, not estimated. No
current-season public or live claim may be made from this source as of this audit. This does
**not** block legitimate historical replay using 2024/25 (fully scored, zero missing results,
verified below) or, in a later slice, 2025/26 once its distinct sub-format is separately
supported.

### 1g. Independent spot-check (verification date 2026-11-02, Australia/Sydney)

Three Matchday 5 (2026/27) results were independently checked against public reporting via web
search — **a factual spot-check only, not a licensing basis for ingesting any of these sources**:

| Fixture | Source file says | Independently corroborated by |
| --- | --- | --- |
| Manchester City v Sunderland (2026-09-20) | 5-3 (3-2 HT) | timesofoman.com, africasoccer.com, littlebigreddot.com — match |
| Brighton & Hove Albion v Arsenal (2026-09-19) | 3-0 (2-0 HT) | Al Jazeera, Vavel, littlebigreddot.com — match |
| Newcastle United v Hull City (2026-09-19) | 2-1 | Football Web Pages, 11v11.com, NewsBytes — match |

**3 of 3 checked matches confirmed correct.** This is a spot check of three matches, not a claim
that all 380 (or even all 50 scored) 2026/27 fixtures were verified — stated explicitly to avoid
the "claim 380 verified when only 5 were inspected" failure mode the brief warned against.

## 2. Secondary/mirror — `openfootball/football.json`

- **Repository:** <https://github.com/openfootball/football.json>
- **Licence:** CC0-1.0 (same public-domain grant as the primary source; same residual-risk note
  applies).
- **2026/27 file:** `2026-27/en.1.json` exists. Its own commit history
  (`gh api 'repos/openfootball/football.json/commits?path=2026-27/en.1.json'`) shows the last
  real update was **2026-09-22T09:33:49Z** — one day *later* than the primary source's last real
  update (2026-09-21), i.e. this mirror lags the primary by at least a day and shows the same
  staleness pattern, not fresher data. This directly confirms the brief's expectation that "a
  mirror is not an independent corroborating source" — it is not treated as one here.
- **Decision:** not used. It adds no freshness benefit over the primary and would only duplicate
  the same stale-after-Matchday-5 gap.

## 3. Secondary/mirror — `footballcsv/england`

- **Repository:** <https://github.com/footballcsv/england>
- **Licence:** CC0-1.0.
- **Repo-level `pushed_at`:** **2023-05-28T13:09:55Z**. Directly listing the repository tree
  confirms the most recent season directory present is `2020s/2020-21` — there is **no 2021/22,
  2022/23, 2023/24, 2024/25, 2025/26, or 2026/27 data at all**. This repository has been inactive
  for over three years relative to this audit's as-of date.
- **Decision:** **REJECT.** Not a viable source for any season this project needs. This is stated
  as a decisive negative finding, not softened — it would be actively misleading to describe this
  as a "secondary" source for current work.

## 4. Potential fresher alternative — `oladeeayo/open-matchday`

- **Repository:** <https://github.com/oladeeayo/open-matchday>
- **Licence:** **None.** GitHub's own licence detection returns `null` — there is no LICENSE file
  in the repository. Under default copyright/database-right rules, "no licence" means **no
  redistribution rights are granted at all**; a public README description of the project's purpose
  is not a substitute for a licence grant.
- **`DISCLAIMER.md`** (read in full) explicitly states: *"This dataset is compiled exclusively
  from free, publicly available sources and is shared for informational, non-commercial use"* and
  *"You may not sell, license, sub-license, or charge for access to this data, in whole or in
  part... You may not present this data as your own commercial data feed."* It also lists five
  distinct upstream providers (football-data.co.uk, fixturedownload.com, OpenLigaDB, ESPN,
  Wikipedia/Wikidata), each with **its own, different terms** — football-data.co.uk and ESPN both
  restrict reuse to personal/non-commercial use; Wikipedia/Wikidata content is CC BY-SA, which
  carries a share-alike obligation this project has not accepted. The disclaimer itself says: *"If
  you plan any use beyond personal, non-commercial consumption — especially redistribution, apps,
  or paid products — check each provider's terms yourself and seek permission from the rights
  holders."*
- **Freshness:** repo `pushed_at` is **2026-11-02** (today) — genuinely fresh, and its stated daily
  update cadence is credible given the commit timestamp. This is real, and more current than the
  primary source. It does not change the rights conclusion.
- **Decision:** **REJECT for any public or redistributed use** — no licence exists, the
  publisher's own disclaimer disclaims commercial/public redistribution rights, and the upstream
  mix includes at least one copyleft-encumbered source (Wikipedia/Wikidata, CC BY-SA) this project
  has not undertaken to comply with. **CONDITIONAL, private-only use permitted**: this source may
  be used as an unpublished, non-redistributed cross-check against the primary source's own
  reported scores (exactly as the brief anticipated — "suitable for private cross-checking only").
  It is not ingested into any tracked dataset, derived report, or export in this slice, and no
  code in this repository fetches it.

## 5. Source comparison table

| Source | Rights (data) | Seasons usable | Latest verified scored date | Rows verified | Update cadence vs reality | Reproducible | Decision |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `openfootball/england` | CC0-1.0, explicit over data | 2023/24–2026/27 (2024/25 & 2026/27 parsed this slice) | 2026-09-20 (2026/27); fully complete through 2025-05-25 (2024/25) | 380/380 (2024/25), 50/50 scored (2026/27) | Weekly commits claimed; actual last real update to the 2026/27 PL file was 6 weeks before this audit | Yes — pinned commit, content-hashed | **ACCEPT** (historical); **current-season status BLOCKED** |
| `openfootball/football.json` | CC0-1.0 | Same seasons, JSON mirror | Lags primary by ≥1 day | Not separately counted (mirror) | Mirrors primary, no independent freshness | Yes | **REJECT as redundant** — adds no corroboration |
| `footballcsv/england` | CC0-1.0 | 1990s–2020/21 only | N/A — no 2024/25+ data exists | 0 (not applicable) | Repo inactive since 2023-05 | N/A | **REJECT** — no current-era data at all |
| `oladeeayo/open-matchday` | **None** (no licence); disclaimer restricts to personal/non-commercial, mixed upstream terms incl. CC BY-SA | 2026/27, daily | 2026-11-02 (today) | Not separately verified (not ingested) | Genuinely fresh, matches its own claim | Not evaluated — rights gate failed first | **REJECT for public use; CONDITIONAL private cross-check only, not used in this slice's code or exports** |

## 6. Bottom line for Slice 01

- The primary source's **data-level** CC0 grant is real, explicit, and verified by reading the
  actual licence and README text, not inferred from a repository-level licence badge.
- The 2026/27 Premier League file is **genuinely stale** (confirmed via per-file commit history,
  not a repo-level timestamp) and is correctly blocked from any "current" or "live" claim.
- 2024/25 is complete, fully scored, and schema-stable in the sub-format this slice's parser
  supports — it is the historical backtest base for later slices.
- Both `footballcsv/england` and `oladeeayo/open-matchday` are rejected for this project's
  purposes, for two different, independent reasons (abandonment vs. no licence/restrictive
  terms) — recorded rather than silently dropped.

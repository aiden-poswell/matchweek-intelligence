# matchweek-intelligence

Status: **Slice 07 in progress — browser-verified product QA and release-readiness review
of the Matchweek Replay Lab preview built in S06.** Nothing in this repository
claims to predict a real, upcoming match outcome. Every forecast this project produces is a
retrospective simulation: "what would a model fit only on results from before date X have said
about fixtures on or after date X" — using match dates, not a validated precise kickoff
timestamp with timezone, so no forecast here was or could have been issued before a match was
actually played.

## What is built (completed slices)

- **S01 — source rights and freshness audit.** `openfootball/england` accepted as a CC0,
  pinned-commit data source. `docs/SOURCE_RIGHTS_AND_PROVENANCE.md`,
  `reports/S01_SOURCE_DECISION.md`.
- **S02 — verified three-season historical corpus.** 2023/24, 2024/25 and 2025/26 Premier
  League seasons (380 fixtures each, 1,140 total) independently validated: exact fixture
  counts, full 20-team double round-robin structural check, score integrity, canonical
  team-identity mapping, calendar-window checks. 2026/27 remains excluded — current and
  partial, never a historical candidate. `docs/DATA_CONTRACT.md`,
  `docs/BACKTEST_INPUT_CONTRACT.md`, `reports/S02_HISTORICAL_CORPUS_AUDIT.md`.
- **S03 — chronological forecasting baselines.** Three predeclared, simple statistical
  baselines (expanding league prior, rolling league frequency, independent team-goal Poisson)
  backtested out-of-time against the 760 held-out 2024/25 + 2025/26 fixtures, using 2023/24 as
  training-only history. `docs/S03_BASELINE_METHODS.md`, `reports/S03_BASELINE_BACKTEST.md`.
- **S04 — attribution and calibration audit.** A fourth, league-only Poisson baseline added to
  decompose where `team_goal_poisson`'s gain comes from; draw-calibration diagnostics across
  both evaluated seasons. `reports/S04_ATTRIBUTION_AUDIT.md`,
  `reports/s04_calibration_diagnostics.json`.
- **S05 — one specified-protocol Dixon-Coles challenger, evaluated and not adopted.** A single
  low-score-correlation challenger (`dixon_coles_team_poisson`), frozen before its result was
  computed, scored against all 760 fixtures. Its point estimate is slightly better than the
  frozen `team_goal_poisson` default, but the descriptive bootstrap interval straddles zero in
  every scope — reported honestly as not strong enough evidence to switch.
  `docs/S05_DIXON_COLES_PROTOCOL.md`, `reports/S05_DIXON_COLES_EVALUATION.md`.
- **S06 — Matchweek Replay Lab: public-data contract + first functional local product.**
  Closing three reproduced review issues from S05 (a backwards bootstrap-sign interpretation
  string, a cross-model fixture/season consistency gap, and a Dixon-Coles zero-boundary
  positivity edge case); building a deterministic public JSON fixture-replay dataset; and a
  static local web preview. Not deployed, not published, no remote added.
- **S07 (this slice) — browser-verified product QA and release-readiness review.** Fixed a
  real route/filter integrity bug (a selected fixture could display under a contradictory
  season or club filter), added runtime validation of the fetched public dataset in the
  browser itself (a second, independent trust boundary beyond the Python generator), fixed a
  real desktop/mobile usability issue (the selected fixture's forecast could sit off-screen
  below a long fixture list), and corrected a second, previously-disclosed-but-deferred copy
  of the S05/S06 bootstrap sign-interpretation bug in `build_attribution_backtest.py` with a
  dedicated erratum (`reports/S07_S04_INTERPRETATION_ERRATUM.md`) and zero numeric drift.
  Verified with real browser automation (Chrome via Playwright), not jsdom alone. Still not
  deployed, not published, no remote added.

## What is explicitly NOT built yet

- No public deployment — the web preview is local-only; no GitHub Pages/Netlify hosting, no
  GitHub remote, no push. S07 verified the app in a real desktop and mobile browser and
  produced a candid go/no-go release checklist (`reports/` S07 exports), but did not deploy.
- No explicit open-source licence for this project's own code (see "Licensing gap" above).
- `dixon_coles_team_poisson` is evaluated but **not adopted** as the default — `team_goal_poisson`
  remains the default, and no further challenger model is planned without a genuinely
  prospective (not hindsight-informed) test.
- No live or current-season (2026/27) forecast of any kind. `live_claim_allowed` is
  hard-coded `False` in `build_data_quality.py`; nothing in this repository can override it.
- No tactical narrative, no betting advice, no market-anchored pricing.

## Status and privacy

Private while under development. No GitHub remote is configured. Source-rights status for
every dataset used is recorded in `docs/SOURCE_RIGHTS_AND_PROVENANCE.md`.

**Licensing gap, disclosed (not yet resolved):** `docs/SOURCE_RIGHTS_AND_PROVENANCE.md` refers
to a `LICENSE.md` "at repo root" containing the CC0 1.0 Universal legal text — that file does
not currently exist in this repository. That CC0 declaration, in any case, was always about
the *source football data* (`openfootball/england`), never about this project's own original
Python and TypeScript/React source code, which currently carries **no explicit licence at
all** (default: all rights reserved). Before any public release, add the actual
`LICENSE.md` this project's docs already reference, and separately and explicitly decide —
rather than silently assume — what licence (if any) covers this project's own original code,
which does not have to be the same licence as the CC0 source data it analyses.

## Setup — Python (forecasting pipeline and data generator)

```
uv sync
uv run pytest -q -rs
```

Console scripts may be blocked by Windows Application Control policy; if so, use
`uv run python -m matchweek_intelligence.<module>` instead.

## Setup — web (Matchweek Replay Lab local preview)

```
cd web
npm ci
npm run typecheck
npm run lint
npm run test
npm run build
npm run preview -- --host 127.0.0.1 --port 4173
```

The preview serves the static production build from `web/dist/` with no Python backend and
no raw source cache required — it reads only the already-generated, tracked
`web/public/data/replays.json`. To regenerate that file from the pinned source cache, run
`uv run python -m matchweek_intelligence.build_public_replay_data` from the repository root.

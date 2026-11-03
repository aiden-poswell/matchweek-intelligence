# matchweek-intelligence

Status: **Slice 03 in progress — chronological forecasting baselines, still historical-only.**
Nothing in this repository claims to predict a real, upcoming match outcome. Every forecast
this project produces is a retrospective simulation: "what would a model fit only on data
available before date X have said about fixtures on or after date X."

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
- **S03 (this slice) — chronological forecasting baselines.** Three predeclared, simple
  statistical baselines (expanding league prior, rolling league frequency, independent
  team-goal Poisson) backtested out-of-time against the 760 held-out 2024/25 + 2025/26
  fixtures, using 2023/24 as training-only history. `docs/S03_BASELINE_METHODS.md`,
  `reports/S03_BASELINE_BACKTEST.md`.

## What is explicitly NOT built yet

- No public website, no PDF, no dashboard, no interactive app.
- No sophisticated challenger model (Dixon-Coles, decay, regularised Poisson) — reserved for
  a later slice, contingent on these simple baselines actually being worth beating.
- No live or current-season (2026/27) forecast of any kind. `live_claim_allowed` is
  hard-coded `False` in `build_data_quality.py`; nothing in this repository can override it.
- No tactical narrative, no betting advice, no market-anchored pricing.

## Status and privacy

Private while under development. No GitHub remote is configured. Source-rights status for
every dataset used is recorded in `docs/SOURCE_RIGHTS_AND_PROVENANCE.md`.

## Setup

```
uv sync
uv run pytest -q -rs
```

Console scripts may be blocked by Windows Application Control policy; if so, use
`uv run python -m matchweek_intelligence.<module>` instead.

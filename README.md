# matchweek-intelligence

Status: **Slice 01 — data feasibility only.** This is a source-rights and data-freshness audit,
not a forecasting model and not a dashboard. Nothing in this repository claims to predict a real
match outcome.

## What this slice actually contains

- An evaluation of candidate open football-results data sources against three questions: what
  rights do we actually have, is the data genuinely current, and is the schema trustworthy enough
  to build on.
- A minimal, source-verified ingestion routine for whichever source(s) pass that evaluation,
  with a pinned commit, a content-hash manifest, and a data-quality report.
- A pre-registered forecasting protocol describing what a later slice would build and how it
  would be evaluated — no model is fitted in this slice.

## What this slice does not contain

- No model, no forecast probabilities, no backtest results, no dashboard, no PDF, no public
  website.
- No claim that any current-season fixture data is complete or fresh unless the audit in
  `reports/s01_source_manifest.json` and `reports/s01_data_quality.json` says so explicitly.

## Status and privacy

Private while under development. No GitHub remote is configured. Source-rights status for every
dataset used is recorded in `docs/SOURCE_RIGHTS_AND_PROVENANCE.md` — nothing is redistributed
publicly until that document says it may be.

## Setup

```
uv sync
uv run pytest -q -rs
```

Console scripts may be blocked by Windows Application Control policy; if so, use
`uv run python -m matchweek_intelligence.<module>` instead.

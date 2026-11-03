# Forecasting protocol — pre-registered in S01, implemented in S03

Status: this document was written in Slice 01, before any model existed, as a design
commitment so a later slice could be checked against it rather than rationalising whatever the
model happened to produce. **Slice 03 implements exactly the three baselines in §"Baselines"
below** (frozen constants in `docs/S03_BASELINE_METHODS.md`) and backtests them out-of-time;
see `reports/S03_BASELINE_BACKTEST.md` for the held-out result. The "candidate models" and
"public product" sections below remain unimplemented, reserved for a later slice.

## Product

A transparent, probabilistic matchweek-intelligence report for one selected league (Premier
League, given Slice 01's source scope). Inputs are limited to results and fixtures from the
approved source, unless a later slice separately approves and rights-clears an additional
source. This is analysis and forecasting, never a betting-tip service, and never a claim of
privileged club access.

## Baselines any model must beat

In increasing sophistication, evaluated on the same chronological splits as any candidate model:

1. **Overall league 1X2 prior** — the historical home/draw/away frequency across the training
   window, applied uniformly to every fixture.
2. **Simple rolling home/draw/away frequency** — recomputed as the training window advances.
3. **A simple goal-rate Poisson model** — independent home/away goal rates per team, no temporal
   decay. **Correction (S03):** "no regularisation" was wrong as originally written — an
   unregularised MLE goal rate is undefined (or wildly unstable) for a promoted club with zero
   or very little prior top-flight history, which this corpus genuinely has every season. S03
   pre-registers a fixed, modest pseudo-match shrinkage toward the contemporaneous league goal
   mean (k=5 pseudo-matches, frozen in `docs/S03_BASELINE_METHODS.md`, never tuned against the
   held-out seasons) as a necessary baseline adjustment for safe estimation — this is still the
   simplest viable version of this model, just not a literal unregularised MLE, and it is
   described honestly as shrunk, not as "no regularisation."
4. **Elo** (optional comparison, not assumed to outperform anything; not implemented in S03).

No sophisticated model is credited as "working" unless it beats baseline (1)-(3) out-of-time, with
an explicit N and confidence interval, not a single point estimate.

## Candidate models (future slices only)

- Regularised attack/defence Poisson with home advantage and temporal decay.
- Dixon-Coles, as an optional, explicitly justified alternative (not a default).
- Elo as a transparent rival/sanity check, not a headline model.

Complexity (Bayesian hierarchical structure, simulation-based features) is reserved until it
demonstrably improves out-of-time evaluation over the above — a complex model that merely fits
better in-sample is not a reason to prefer it.

## Evaluation discipline

- **Strict chronology.** Every model fit may see only results strictly before each prediction
  cutoff, AND only rows that are actually scored. The training-safe helper is
  `chronology.completed_training_results_as_of(records, cutoff_date)` — NOT `as_of_filter()`
  alone, which is status-agnostic and can still return a `result_missing` row that happens to
  be chronologically in the past (see `docs/DATA_CONTRACT.md` for why the two helpers have
  deliberately different contracts). Same-day fixtures are always a simultaneous batch — a
  model is never trained on an earlier same-day result before predicting another same-day
  fixture, since this source carries no reliable kickoff-time field to order within a day.
  `tests/test_chronology.py` proves the exclusion mechanism with synthetic fixtures;
  `src/matchweek_intelligence/model_inputs.py` (S03) is the actual walk-forward training loop.
- **Expanding or rolling backtests**, evaluated per-season and overall, with explicit sample
  sizes (N) reported alongside every metric — never a metric without its N.
- **Metrics:** 1X2 probability vectors must sum to 1 (a hard assertion, not a convention); log
  loss; multiclass Brier score; Ranked Probability Score; calibration/reliability curves where
  sample size permits (season-level N is small — roughly 380 matches/season for the Premier
  League — so calibration claims below a reasonable minimum N must be flagged as low-powered,
  not suppressed).
- **No in-sample victory declarations.** A model is only described as "better than baseline" using
  held-out, chronologically later fixtures than anything it was fit on.

## Promotions and new teams

A promoted club's cold-start strength prior must be documented explicitly (e.g. a shrunk-toward-
average prior, or a separate lower-division history if that data source and team-identity mapping
is itself validated in a later slice). It is never silently borrowed from that club's *future*
top-flight performance, and a promoted club is never described as having "Premier-League-only"
history when prior Championship results exist and are simply not yet ingested.

## Public product (explicitly out of scope for this slice)

An eventual public, original-design report showing historical holdout skill, next-matchweek
outcome probabilities, model uncertainty, and an explicit source as-of date — gated on
`live_claim_allowed = True` for the current-season source (S02 replaced the single, fail-open
S01 field `current_season_publishable` with three separated fields; `live_claim_allowed` is the
one that gates any live/public claim, and it is hard-coded `False` in `build_data_quality.py`
as of this slice — there is no mechanism in this repository that can currently set it `True`).
Never switch to a source with worse rights to manufacture a "yes." Every public prediction must
state its scenario assumptions and unplayed-match coverage plainly. This remains analysis, not a
betting system, and nothing in this protocol authorises publishing anything.

## Professional narrative, not decorative insight

Questions this product should actually try to answer: which fixture outcomes are genuinely
uncertain; where a model disagrees with the naive baseline and whether that disagreement is
earned historically; how sensitive the probabilities are to plausible alternative team-strength
assumptions. This explicitly excludes inventing tactical narrative from a scoreline alone — this
source has no tactical, event, or tracking data, so no tactical claim can be grounded in it.

## Stop conditions

- Insufficient matches in the training window for the league/season in question.
- Missing or ambiguous date chronology (a file that fails `detect_subformat` cleanly, or any
  `result_missing` row reaching `completed_training_results_as_of` — which must never happen
  by construction, since that helper filters on `status == "played_with_score"`).
- Source rights not cleared for the intended output (public vs. private).
- A candidate model backtesting worse than the baselines in §"Baselines" above, on held-out data.

## What would make this convincing, interview-defensible work

A public holdout performance table with explicit Ns, calibration plots that are allowed to show a
model is *not* well-calibrated in some region, an honest statement of what the source cannot
support (no xG, no injuries, no tactical read), and a visible paper trail from pinned source
commit through parsed records through backtest result — every number traceable back to code, never
hand-typed. A glossy report with an unstated
as-of date or a model that was never checked against a trivial baseline is the opposite of this.

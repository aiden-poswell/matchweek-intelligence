# S03 baseline backtest — held-out result

Entirely historical. Nothing here is a live forecast: every number is a retrospective
out-of-time simulation over already-completed Premier League fixtures (2024/25 and 2025/26),
trained only on data strictly before each prediction date. 2026/27 does not appear anywhere in
this corpus. Full method freeze: `docs/S03_BASELINE_METHODS.md`. Full numbers:
`reports/s03_baseline_backtest_metrics.json`. Per-fixture audit (not tracked in Git):
`data/processed/s03_backtest_predictions_REVIEW.csv`.

## Evaluation setup

- Training-only: 2023/24 (380 fixtures, never predicted).
- Evaluated: every 2024/25 fixture (380) and every 2025/26 fixture (380). **N = 760, exactly,
  no exclusions.**
- Source: `openfootball/england`, pinned commit `9ee7a0c351805c99cc334478a9bf04b7d0432fec`.
- Three predeclared baselines, frozen before this backtest was run: expanding league 1X2 prior,
  rolling (last ~100 fixture) league 1X2 frequency, and an independent team-goal Poisson model
  with k=5 pseudo-match shrinkage.

## Headline result

| Model | Log loss | Brier | RPS | Top-class accuracy (context only) |
| --- | --- | --- | --- | --- |
| Expanding league prior | 1.0833 | 0.6563 | 0.2317 | 41.7% |
| Rolling league frequency | 1.0943 | 0.6631 | 0.2342 | 39.7% |
| **Team-goal Poisson** | **1.0147** | **0.6078** | **0.2081** | **50.1%** |

N=760 for every figure above. The Poisson baseline wins on every proper score, overall and in
each evaluated season individually (see the season breakdown below). **This was not forced or
cherry-picked** — Stage C's protocol explicitly allowed for, and S01's forecasting protocol
explicitly anticipated, the possibility that it could lose; it did not.

## Season-by-season breakdown (N=380 each)

| Season | Model | Log loss | Brier | RPS |
| --- | --- | --- | --- | --- |
| 2024/25 | Expanding prior | 1.0823 | 0.6563 | 0.2354 |
| 2024/25 | Rolling frequency | 1.0977 | 0.6655 | 0.2385 |
| 2024/25 | Poisson | 0.9972 | 0.5957 | 0.2058 |
| 2025/26 | Expanding prior | 1.0842 | 0.6562 | 0.2280 |
| 2025/26 | Rolling frequency | 1.0910 | 0.6607 | 0.2300 |
| 2025/26 | Poisson | 1.0323 | 0.6200 | 0.2105 |

The Poisson advantage is larger in 2024/25 than 2025/26 (log-loss gap of 0.085 vs. 0.052) — a
real, visible difference between the two held-out seasons, not something the backtest
smooths away.

## Honest comparison with uncertainty (paired date-block bootstrap, seed=20250103, 1000 replicates)

Differences below are `log_loss(model) - log_loss(expanding prior)` — negative means the other
model beat the expanding prior; the interval is a **descriptive, approximate** 95% range, never
a formal significance test:

| Comparison | Overall diff | 95% descriptive interval |
| --- | --- | --- |
| Rolling frequency − Expanding | **+0.0111** | [+0.0005, +0.0215] |
| Poisson − Expanding | **−0.0685** | [−0.0929, −0.0434] |

**Two real findings, stated plainly:**

1. **The rolling-window frequency baseline is, if anything, slightly worse than the simplest
   expanding prior**, and the interval barely excludes zero. A ~100-fixture recency window did
   not help here relative to using the full expanding history — more training data beat a
   recency-weighted window in this comparison. This is worth taking at face value rather than
   explaining away: Premier League team-level and league-level base rates over a 1-3 season
   horizon did not drift fast enough for the rolling window's narrower lens to pay for its
   smaller effective sample.
2. **The Poisson baseline's advantage over the expanding prior is real and consistent** — the
   interval is entirely on the "Poisson wins" side in both the overall comparison and in each
   individual season (not shown above but confirmed in the JSON). This is the expected result
   for a model that actually uses team identity, not just league-wide base rates, and it is
   reported as a real, useful finding, not an assumption.

These intervals describe the uncertainty in this specific held-out sample; they are not
evidence of a causal "better model" claim and should not be read as a formal hypothesis test.

## Cold-start behaviour (promoted / returning teams)

Four fixtures in the evaluation set involve a HOME team with **zero** training-corpus exposure
(no appearance anywhere in 2023/24, or earlier in the same season, before that date): Ipswich
Town (2024-08-17, home vs. Liverpool), Leicester City (2024-08-19, home vs. Tottenham Hotspur),
Sunderland (2025-08-16, home vs. West Ham United), and Leeds United (2025-08-18, home vs.
Everton). One fixture has a cold-start AWAY team: Southampton (2024-08-17, away at Newcastle
United). All five resolved to finite, valid probability vectors by construction (the k=5
Poisson shrinkage falls back to the league-wide goal mean exactly when a team has zero
training matches — verified directly in `tests/test_baseline_models.py`).

**A genuine subtlety, stated honestly rather than glossed over:** "cold start" here means "zero
appearances anywhere in this project's three-season training corpus (2023/24 onward)," not
"zero Premier League history ever." Burnley — relegated after 2023/24, absent from 2024/25,
promoted back for 2025/26 — is NOT flagged cold-start for its 2025/26 fixtures, because its
2023/24 matches are still present in the training corpus and still inform its (heavily shrunk,
two-seasons-old) rate estimates. Leeds United and Sunderland, by contrast, have no appearance in
any of the three eligible seasons before their promoted-season fixtures, so they are genuinely
cold-start by this corpus's own evidence. A reader should treat the Poisson model's predictions
for these specific fixtures as close to the pure league-average prior, not as informed
team-specific forecasts — the per-fixture CSV's `*_exposure` and `*_cold_start` columns make
this checkable for every one of the 760 evaluated fixtures, not just these five.

## Method limitations, stated plainly

- No temporal decay, no Dixon-Coles low-score correlation, no expected-goals feature, no
  bookmaker/market data — deliberately the simplest viable version of each idea.
- The Poisson model assumes home and away goals are independent given the two teams' rates;
  real matches have some correlation (e.g. game-state effects) this model cannot capture.
- Only N=760 held-out fixtures across two seasons; season-level calibration claims below a
  reasonable sample floor should be treated as indicative, not conclusive.
- `top_class_accuracy` is reported as context only and was never used to select or favour any
  model ahead of the three proper scores above.

## What this result justifies, and what it does not

It justifies carrying the independent team-goal Poisson model forward as the benchmark any
future, more sophisticated challenger (Dixon-Coles, decay, regularised multi-team Poisson) must
actually beat out-of-time — not assumed to beat, demonstrated to beat, the same way this
baseline just demonstrated beating the two frequency baselines. It does **not** justify, and
nothing in this report should be read as supporting, any public-facing product, live forecast,
or claim about the current 2026/27 season. `live_claim_allowed` remains hard-coded `False`
throughout this repository.

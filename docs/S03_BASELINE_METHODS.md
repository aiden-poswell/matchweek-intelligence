# S03 baseline methods — frozen before inspecting any held-out result

Every constant below is fixed here, before `reports/S03_BASELINE_BACKTEST.md` was written and
before any held-out metric was computed. None of these constants were tuned against the 760
held-out 2024/25+2025/26 fixtures — this document, together with the frozen source code, is
the record that makes that claim checkable.

## Fixture grain and chronology

- One row = one fixture: `(competition, season, match_date, home_team, away_team)`, canonical
  team names only (`team_identity.canonical_team_name`).
- Evaluation schedule (frozen): 2023/24 is training-only. Every one of the 380 2024/25 fixtures
  and every one of the 380 2025/26 fixtures is predicted. N=760 total, N=380 per season, no
  exclusions.
- At calendar date `d`, training data is exactly
  `chronology.completed_training_results_as_of(all_eligible_historical_records, d)` — never
  `as_of_filter` alone. Every fixture scheduled on date `d` uses the IDENTICAL training set
  (same-day fixtures are a whole batch, never partially included); the training set only grows
  for dates strictly after `d`.
- 2026/27 is never loaded (`model_inputs.ELIGIBLE_SEASONS` excludes it structurally) and never
  appears in training or evaluation.
- A promoted/new team with zero or very little prior history gets a league-average cold-start
  prior through the same k=5 pseudo-match shrinkage used for every team (see "Poisson" below) —
  not a special case, not a borrowed future/lower-division record.

## Baseline 1 — expanding league 1X2 prior

For fixtures on date `d`: count `H`, `D`, `A` outcomes over the training set (all fixtures with
`match_date < d`, status `played_with_score`). Apply symmetric Laplace/Dirichlet smoothing with
**alpha = 1** (frozen, never tuned):

```
P(H) = (H + alpha) / (H + D + A + 3*alpha)
P(D) = (D + alpha) / (H + D + A + 3*alpha)
P(A) = (A + alpha) / (H + D + A + 3*alpha)
```

Applied uniformly to every fixture on date `d`, regardless of which teams are playing.

**Check (frozen before implementation, verified after):** the first 2024/25 forecast date
trains on exactly the 380 completed 2023/24 fixtures, `H=175, D=82, A=123`. The smoothed vector
must be `(176, 83, 124) / 383`.

## Baseline 2 — rolling league 1X2 frequency

Same smoothing formula as Baseline 1, but applied only to a bounded recent window instead of
the full expanding history.

**Window rule (frozen):** target size **100** completed fixtures. Walk backward through the
training set (already sorted ascending by date) by whole match-date batches, starting from the
most recent batch before `d`, accumulating fixtures until the running total is **>= 100**,
including the ENTIRE date-batch that crosses the threshold (never split a date-batch — this is
the "avoid arbitrary within-date truncation" rule). If the entire training set has fewer than
100 completed fixtures, use all of it (this is a safety branch; with 380 training fixtures
available from the first 2024/25 forecast date onward, it is never exercised in the real
evaluation — tested only synthetically).

This produces a materially different H/D/A count than the expanding baseline from early in
2024/25 onward. **Correction (S04):** this document originally said "100 fixtures is roughly
2.5 matchdays," which was simply wrong arithmetic — a 20-club double round-robin plays 10
fixtures per standard matchweek, so 100 fixtures is roughly **ten** standard matchweeks' worth,
not 2.5. Stated as an approximation deliberately: real rearranged fixtures (see
`reports/S02_FORMAT_AUDIT.md` and `docs/DATA_CONTRACT.md`) mean a given match-date batch does
not always align exactly with a single matchweek label, so "ten matchweeks" is a scale
description, not a claim that the rolling window's 100-fixture boundary lands on a clean
matchweek-10 cut. By the time training history exceeds ~100 fixtures the two baselines
diverge — verified directly in `tests/test_baseline_models.py`, not assumed.

## Baseline 3 — independent team-goal Poisson, with frozen pseudo-match shrinkage

**Correction, stated plainly (see `reports/S03_PROTOCOL_ALIGNMENT.md` item 2e):** S01's
original protocol described this as having "no regularisation." That is not what is
implemented, and claiming it would be false: an unregularised MLE goal rate is undefined for a
team with zero training matches (division by zero) and wildly unstable for a team with one or
two. This baseline uses a fixed, modest **k = 5 pseudo-match shrinkage** toward the
contemporaneous league goal mean for every team-specific rate — frozen here, never tuned
against the held-out seasons, and described honestly as a shrunk baseline.

### League-wide means (from the training set only)

```
league_home_mean = mean(home_score) over all completed training fixtures
league_away_mean = mean(away_score) over all completed training fixtures
```

**Safe fallback (frozen, defensive only):** if the training set is empty (zero completed
fixtures — never true from the first real 2024/25 forecast date onward, since 2023/24 alone
supplies 380), both league means fall back to **1.5** goals, a round, clearly-a-prior constant,
not fitted from any data. Tested synthetically; never exercised in the real backtest.

### Team-specific rates, each shrunk toward the matching league mean with k=5

For team `X`, computed from `X`'s own completed training fixtures only:

```
H_for(X)      = (sum of goals X scored at home      + k * league_home_mean) / (n_home(X) + k)
H_conceded(X) = (sum of goals X conceded at home     + k * league_away_mean) / (n_home(X) + k)
A_for(X)      = (sum of goals X scored away          + k * league_away_mean) / (n_away(X) + k)
A_conceded(X) = (sum of goals X conceded away        + k * league_home_mean) / (n_away(X) + k)
```

Shrinkage direction is fixed by which side of the ball each quantity measures: `H_for` and
`A_conceded` are both "goals scored by a team playing at home" quantities (on the home scale,
shrunk toward `league_home_mean`); `H_conceded` and `A_for` are both "goals scored by a team
playing away" quantities (on the away scale, shrunk toward `league_away_mean`). A team with
`n_home(X) = 0` or `n_away(X) = 0` (a brand-new promoted club, before it has played either
venue) gets exactly the league mean for that component — finite by construction, never a
division by zero, never a special-cased branch.

### Fixture lambda (independent Poisson, home/away goals independent of each other)

For fixture `home = H`, `away = A`:

```
lambda_home = H_for(H) * A_conceded(A) / league_home_mean
lambda_away = A_for(A) * H_conceded(H) / league_away_mean
```

No temporal decay, no Dixon-Coles low-score correlation adjustment, no expected-goals feature —
deliberately the simplest version of this idea.

### Scoreline probabilities and the explicit tail bound

`P(home_goals=i) = Poisson(i; lambda_home)`, independently `P(away_goals=j) = Poisson(j;
lambda_away)`. Sum over the joint grid up to a cap `M`, increasing `M` from a small starting
value until the neglected tail mass is below the frozen bound:

```
included_mass(M) = CDF_home(M) * CDF_away(M)
tail(M) = 1 - included_mass(M)
```

**Frozen tail bound: tail(M) <= 1e-10** (safety cap `M <= 100` to guarantee termination; never
expected to bind for realistic Premier League lambdas, tested synthetically with a large finite
lambda to confirm the cap is never silently hit in practice).

H/D/A are then the sums `sum_{i>j} P(i)P(j)`, `sum_{i=j} P(i)P(j)`, `sum_{i<j} P(i)P(j)` over the
included `i, j <= M` grid, **normalised by dividing by `included_mass(M)`** so the three values
sum to exactly 1. `lambda_home`, `lambda_away`, `included_mass(M)`, and the raw `tail(M)` value
are all computed and held in `Prediction.diagnostics` for every Poisson prediction — this was
never in doubt; the model always computes them internally.

**Correction (S04):** this document previously said these trace fields "are recorded per
fixture in the review export." That was an export/documentation discrepancy, not a modelling
error: the actual S03 CSV (`data/processed/s03_backtest_predictions_REVIEW.csv`, 21 columns)
does not contain `lambda_home`, `lambda_away`, `tail_mass`, `included_mass`, or `max_goals` —
only the three final, already-normalised probabilities and the per-fixture proper-score values
derived from them. This does NOT mean the probabilities are wrong (independently re-verified to
sum to 1 within the stated tolerance for every one of the 760 Poisson predictions — see
`reports/S03_PROTOCOL_ALIGNMENT.md` / S03 verification); it means the diagnostic trace columns
promised here were never actually exported. The frozen S03 CSV is **not** being rewritten to
add them retroactively. S04's new four-model export
(`data/processed/s04_ablation_predictions_REVIEW.csv`) adds these exact trace columns for both
Poisson models going forward, and this document's promise now accurately describes that export,
not the historical S03 one.

## Numeric validity (all three baselines)

Every returned `[P(H), P(D), P(A)]` must be finite, strictly positive (required for log-loss),
and sum to 1 within **1e-9** absolute tolerance. A baseline implementation that cannot produce
a valid vector for some input must raise, not silently clip — clipping exists only as an
explicitly declared evaluation guard against floating-point sum drift of the order of 1e-9–1e-12
from repeated normalisation, never as a cover for a genuinely broken probability.

## Scoring conventions (frozen, implemented independently in `metrics.py`)

- **Log loss:** `-log(p_observed)` per fixture, averaged, with N reported.
- **Multiclass Brier:** `sum_k (p_k - 1[y=k])^2` per fixture (the three-component
  sum-of-squared-errors definition over H/D/A), averaged over fixtures. This is **twice**
  scikit-learn's two-class Brier convention in the binary case and is stated explicitly to avoid
  a silent comparison error against a different library's number.
- **Ranked Probability Score (RPS):** outcome order fixed as **H, D, A** (home win treated as
  the "low" ordinal category, away win as "high" — an arbitrary but FIXED convention, stated
  here rather than left implicit). Let cumulative predicted `C1 = P(H)`, `C2 = P(H)+P(D)`, and
  cumulative observed `O1, O2` (0 or 1 at each boundary based on the actual outcome's position).
  `RPS = ((C1-O1)^2 + (C2-O2)^2) / 2`. Frozen and checked against hand-computed tiny examples in
  `tests/test_metrics.py` before use on real data.
- **Top-class accuracy:** reported as context only. Never used to select or headline a model
  ahead of the three proper scores above.

## Uncertainty quantification

95% descriptive intervals for log-loss differences between two models use a **paired, fixed-seed
(seed=20250103), date-block bootstrap**: resample entire evaluation match-dates (not individual
fixtures) within each evaluation season, same resampled date-index applied to both models being
compared, **>= 1000 replicates**. These intervals are explicitly labelled **descriptive and
approximate**, never a formal hypothesis test and never evidence of causal superiority from a
small point difference.

## What this baseline set deliberately excludes

No Elo, no Dixon-Coles correlation adjustment, no temporal decay, no expected goals, no
bookmaker/market data, no tactical narrative. It is valid and expected that the Poisson baseline
may lose to one of the two frequency baselines out-of-time — that result, if it occurs, is
reported as a real finding, not hidden or re-tuned away.

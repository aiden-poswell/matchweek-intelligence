# S05 Dixon-Coles evaluation — one pre-registered challenger, honestly scored

Entirely historical. **This is an exploratory, hindsight-informed chronological replay, not a
pristine prospective holdout** — both evaluated seasons' outcomes have already been inspected
repeatedly across S03, S04, and S05. Nothing here is a live forecast; `live_claim_allowed`
remains hard-coded `False`. Full method freeze: `docs/S05_DIXON_COLES_PROTOCOL.md`, written and
committed BEFORE this model was fitted. Full numbers: `reports/s05_challenger_metrics.json`,
`reports/s05_rho_fit_audit.json`. Per-fixture audit (not tracked in Git):
`data/processed/s05_challenger_predictions_REVIEW.csv` (3,800 rows = 760 fixtures × 5 models).

## Headline result (N=760)

| Model | Log loss | Brier | RPS | Accuracy (context only) |
| --- | --- | --- | --- | --- |
| Expanding league prior | 1.0833 | 0.6563 | 0.2317 | 41.7% |
| Rolling league frequency | 1.0943 | 0.6631 | 0.2342 | 39.7% |
| League-only Poisson | 1.0817 | 0.6553 | 0.2314 | 41.7% |
| **Team-goal Poisson (frozen S03 default)** | **1.0147** | **0.6078** | **0.2081** | **50.1%** |
| **Dixon-Coles team Poisson (challenger)** | **1.0136** | **0.6071** | **0.2080** | **50.1%** |

The challenger improves on every proper score, by a small margin, in exactly the direction
the draw-underprediction diagnostic (S04) suggested it might.

## The honest statistical verdict: not strong enough evidence to switch

Paired date-block descriptive bootstrap, seed=20250103, 1000 replicates, `dixon_coles_team_poisson
− team_goal_poisson` (negative = challenger wins):

| Scope | Point diff (log loss) | 95% descriptive interval |
| --- | --- | --- |
| Overall (N=760) | **−0.00113** | **[−0.00275, +0.00050]** |
| 2024/25 (N=380) | −0.00065 | [−0.00302, +0.00175] |
| 2025/26 (N=380) | −0.00161 | [−0.00390, +0.00058] |

**The point estimate favours the challenger in every scope, consistently, and the direction
matches theory (see below) — but every one of the three descriptive intervals straddles zero.**
Per the pre-registered adoption rule (`docs/S05_DIXON_COLES_PROTOCOL.md`: "the ONE challenger
evaluated... If it loses, the conclusion is that the more complex model has not earned adoption
in this replay"), this is reported as: **a small, directionally-consistent, but not
statistically unambiguous improvement.** This is not strong enough evidence to replace the
simpler, already-validated `team_goal_poisson` as the default.

**Recommendation: keep `team_goal_poisson` as the public demo's forecasting default.**
`dixon_coles_team_poisson` is a documented, promising candidate for a future genuinely
prospective test — not a replacement earned by this replay alone, and not something to retune
or re-test against the same two seasons to try to tip the interval.

## Draw calibration — did it actually narrow?

| Model | Predicted P(D) | Observed P(D) | Gap (pp) |
| --- | --- | --- | --- |
| Team-goal Poisson | 22.38% | 25.92% | +3.54 |
| Dixon-Coles team Poisson | 23.25% | 25.92% | **+2.67** |

The gap narrows by about 0.87pp. **This is reported as a descriptive observation, not as
evidence the challenge "fixed" draw calibration or that the low-score mechanism is the real
cause of the original gap** — S04 already named three indistinguishable candidate explanations
(independence/low-score handling, a shifted league draw base rate, sampling variation), and
this result alone cannot separate them. The equal-count bins below (152 fixtures each, same
sorting/tie-break convention as S04) show the same pattern as before: no clean monotonic
miscalibration, bin 3 again reads slightly over- rather than under-predicted.

| Bin | N | Predicted P(D) range | Mean predicted % | Observed % |
| --- | --- | --- | --- | --- |
| 0 | 152 | 0.091 – 0.201 | 17.70 | 17.76 |
| 1 | 152 | 0.202 – 0.227 | 21.62 | 26.32 |
| 2 | 152 | 0.227 – 0.244 | 23.63 | 28.29 |
| 3 | 152 | 0.244 – 0.263 | 25.32 | 24.34 |
| 4 | 152 | 0.264 – 0.320 | 27.96 | 32.89 |

**Primary adoption rule, restated:** improvement in properly scored 1X2 probabilities is what
matters — the draw gap narrowing is consistent with, but not a substitute for, the (ambiguous)
log-loss result above. A smaller aggregate draw percentage gap, by itself, is never treated as
sufficient to call this model better.

## The fitted rho — is it doing something theoretically sane?

223 unique evaluation dates, every one `fit_status = "fitted_interior"` (zero
`insufficient_history`, zero boundary hits — confirmed directly in
`reports/s05_rho_fit_audit.json`). `rho` is **consistently negative** across the whole
evaluation window: min −0.0747, median −0.0443, max −0.0121. A negative `rho` increases
`tau(0,0)` and `tau(1,1)` (pushes mass toward 0-0/1-1 draws) and decreases `tau(1,0)`/`tau(0,1)`
— exactly the direction that would be expected given team_goal_poisson's own measured draw
under-prediction. This internal consistency is a genuine, checkable sanity signal that the fit
is doing something theoretically coherent, not an independent confirmation that the correction
is "right" in any stronger sense.

## What this does and does not establish

- **Does establish:** a correctly-implemented, leak-free, walk-forward Dixon-Coles correction
  produces a small, directionally consistent, theoretically sane improvement over frozen
  `team_goal_poisson` in this specific replay — and that this improvement, while real as a point
  estimate, is not large enough to be distinguishable from zero by this descriptive bootstrap at
  N=760.
- **Does not establish:** that Dixon-Coles corrections generally help independent-Poisson
  football models, that the draw-calibration gap is caused specifically by goal-score
  dependence (vs. a shifted base rate or noise), or any formal statistical significance.
- **Does not change** any S03 or S04 figure — all four non-challenger models' predictions in
  the S05 export are copied verbatim from `build_attribution_backtest.run_attribution_backtest`,
  verified field-for-field identical to the frozen S04 CSV for all 3,040 shared rows.

## A genuine implementation finding, disclosed (not hidden)

Building the prequential lambda cache required for leak-free `rho` fitting surfaced a real edge
case the protocol had not anticipated: the very earliest 2023/24 training matches have too
little history for even `team_goal_poisson`'s own existing league-mean validation to produce a
usable value. This is documented as an addendum to `docs/S05_DIXON_COLES_PROTOCOL.md`, frozen
before any evaluation result was computed: those few matches are simply excluded from the
prequential cache (never assigned an invented lambda pair), with zero effect on any evaluated
fixture's own prediction.

## Limitations, stated plainly

- N=760 across two seasons only. The per-season intervals are each wider than the overall one,
  as expected, and both still straddle zero.
- The bootstrap intervals are descriptive and approximate throughout — never a formal
  significance test, never evidence of causal superiority.
- `rho` is fitted once per evaluation date and shared across every fixture that day — it is not
  a per-team or per-fixture parameter, by design.
- This remains, unavoidably, hindsight-informed: the humans running this replay already knew
  about the draw-underprediction finding before choosing to test exactly the correction that
  targets it. `docs/S04_CHALLENGER_RESEARCH_PLAN.md` and `docs/S05_DIXON_COLES_PROTOCOL.md` both
  disclose this; a genuinely prospective test would require new, rights-cleared future data or
  a time-stamped frozen submission made before any new outcome is known.

## Decision

**Keep `team_goal_poisson` as the forecasting default for the forthcoming Matchweek Replay
Lab** (see `docs/S05_PUBLIC_PRODUCT_BRIEF.md`). The Dixon-Coles challenger did not clearly earn
adoption in this replay — a real, useful, negative-leaning-positive result, reported as such,
not hidden and not re-tuned to try to win.

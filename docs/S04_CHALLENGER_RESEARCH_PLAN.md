# S04 challenger research plan — proposal only, nothing implemented here

Status: this document proposes what **S05** would build. **No Dixon-Coles, Elo, or decay model
is fitted, implemented, or selected anywhere in S04.** It is grounded in the actual S03/S04
diagnostics, not a generic textbook recipe pasted in without reference to this project's real
findings.

## Primary hypothesis: a modest Dixon-Coles-style low-score correction

### Motivation, from actual S04 evidence

`reports/S04_CALIBRATION_AND_FAILURES.md` found `team_goal_poisson` under-predicts draws by
+3.54pp overall (observed − predicted), the largest gap of the four S04 models, while still
having the best overall log loss of the four. The classic Dixon-Coles (1997) motivation is
exactly this pattern: independent Poisson goal models systematically under-weight low-scoring
outcomes (especially 0-0 and 1-1 draws) because real match goals are not quite independent —
teams play differently once the scoreline is close and low. This project's own diagnostic
reproduces the textbook symptom, which is a reasonable (not automatic) basis for trying the
textbook fix.

**What the available data do NOT establish:** that a Dixon-Coles correction *will* fix this,
that the draw gap is caused by goal dependence rather than a shifted league-wide draw base rate
or sampling variation (§3 of the calibration report lists three indistinguishable candidate
causes), or that any log-loss/calibration improvement from it will be large enough to matter
in practice. This is a hypothesis to TEST in S05, not a result assumed here.

### Proposed likelihood and parameterisation

Dixon-Coles multiplies the independent-Poisson joint probability by a correlation adjustment
`tau(i, j; rho)` applied only to low scorelines (classically `i, j in {0, 1}`):

```
tau(0, 0) = 1 - lambda_home * lambda_away * rho
tau(1, 1) = 1 - rho
tau(1, 0) = 1 + lambda_away * rho
tau(0, 1) = 1 + lambda_home * rho
tau(i, j) = 1 otherwise
```

`rho` is a single new free parameter, estimated ONLY from training data (never from the 760
held-out fixtures). **Constraint that must be enforced, not assumed:** after applying `tau`,
the resulting joint distribution over `(i, j)` must still be renormalised to sum to 1 over the
same goal grid `team_goal_poisson` already uses (reusing
`baseline_models._poisson_outcome_distribution`'s grid/tail-bound machinery, extended with the
`tau` multiplier before the H/D/A aggregation step) — a raw Dixon-Coles adjustment can produce
small negative joint "probabilities" for extreme `rho` values, which must be rejected (fail
closed), not clipped silently.

### Parameter identification and leak-free fitting protocol

- `rho` would be fit by maximum likelihood on the SAME expanding training set
  `completed_training_results_as_of` already produces for each as-of date — no change to the
  chronology discipline.
- Critically: fitting `rho` is a MODEL-FITTING step, which S03/S04's categorical and
  unregularised-shrinkage baselines never needed. S05 must decide, and pre-register BEFORE
  looking at 2024/25 or 2025/26 results again, whether `rho` is:
  (a) re-fit at every as-of date (fully walk-forward, most leak-free, most expensive), or
  (b) fit once on 2023/24 only and held fixed for the whole evaluation (cheaper, simpler, but a
  real choice to defend, not a default).
  This decision must be frozen in a methods document analogous to
  `docs/S03_BASELINE_METHODS.md`, BEFORE any S05 held-out number is computed.
- `rho` must be bounded to keep every `tau(i,j)` term non-negative for the realistic lambda
  range this corpus produces (checked, not assumed) — an unconstrained MLE could wander outside
  the valid region.

### Promoted-team handling

Unchanged from S03/S04: the existing k=5 pseudo-match shrinkage toward league means remains the
cold-start mechanism for `lambda_home`/`lambda_away`. `rho` itself is a single league-wide
parameter (not team-specific), so it carries no additional cold-start risk by construction.

### Computational budget

A single-parameter 1-D likelihood search per as-of date (if walk-forward) over ~82 unique
evaluation dates across two seasons is computationally trivial (well under a second per date on
the existing dataset size) — this is not a budget-driving decision; the leak-free-vs-fixed
choice above is about methodological defensibility, not compute cost.

### Evaluation vs. the frozen benchmark

The frozen benchmark is `team_goal_poisson`'s existing S03 numbers (log loss 1.0147 overall),
never retuned. S05 would report: overall and per-season log loss/Brier/RPS for the Dixon-Coles
variant vs. `team_goal_poisson`, the SAME paired date-block bootstrap methodology already used
in S03/S04 (fixed seed, resampled whole dates), and — specifically — whether the draw
calibration gap measured in `reports/S04_CALIBRATION_AND_FAILURES.md` actually narrows, using
the identical mean-predicted-vs-observed and equal-count-bin methodology from this slice, not a
new ad hoc calibration metric invented to flatter the new model.

## Alternative: team-strength temporal decay or Elo

### Temporal decay (exponential down-weighting of older results)

Reason to consider: `rolling_league_frequency`'s S03 result (slightly WORSE than the expanding
prior) suggests a hard recency cutoff doesn't help at this corpus's scale — but a smooth decay
weight is a different, less abrupt mechanism than a hard window, and has not been tested here.
Reason to be cautious: it introduces a second new free parameter (half-life) on top of
Dixon-Coles' `rho`, and S03's one actual recency experiment underperformed, which is modest
real evidence against prioritising a recency mechanism first.

### Elo

Reason to consider: genuinely simple, transparent, well-understood, pre-registered as optional
in S01. Reason to deprioritise for the FIRST S05 attempt: Elo alone does not produce a full
scoreline distribution the way the Poisson family does, so it would need its own separate
1X2-mapping step (e.g. a logistic link), which is a different kind of modelling choice than
directly addressing the specific, already-diagnosed draw-calibration gap. Recommendation:
Dixon-Coles first, because it directly targets a weakness this project has actually measured;
Elo remains a reasonable SECOND challenger or a transparent sanity-check rival, not the primary
S05 hypothesis.

## Hindsight disclosure — this is not a pristine holdout going forward

Both 2024/25 and 2025/26 outcomes and every S03/S04 model's scores against them have now been
inspected, repeatedly, by the people building this project. **Any S05 comparison on these same
two seasons is an exploratory, retrospective out-of-time replay — not a blind, prospective
test.** This is explicitly disclosed, not hidden: the chronological as-of discipline
(`completed_training_results_as_of`) still prevents a MODEL from using future information
relative to its own prediction date, but it does NOT prevent the HUMAN researcher from having
already seen which fixtures were hard, which model won, and where the draw gap showed up —
and then choosing a challenger informed by exactly that. A genuinely blind final evaluation
would require one of:

1. **New, not-yet-scored fixtures** — i.e. a future season, once its rights are cleared and its
   source passes the same freshness/completeness gates 2026/27 currently fails
   (`live_claim_allowed` remains hard-coded `False`; nothing here changes that).
2. **A prospectively frozen, time-stamped submission** of the exact S05 model specification
   (architecture, parameters, fitting protocol) BEFORE any new outcome becomes available to
   compare it against — effectively a pre-registration discipline one level stronger than this
   document already practises for constants, extended to cover the model class itself.

Until one of those exists, every number this project reports about 2024/25 and 2025/26 — in
S03, S04, or a future S05 — is retrospective model development, not a holdout in the strict
sense, and every report should keep saying so plainly rather than letting the phrase "held-out"
imply more blindness than the process actually has.

## Not done in S04 (explicit)

No Dixon-Coles `rho` was estimated. No decay half-life was chosen or tested. No Elo rating was
computed. No new free parameter of any kind was fit against 2024/25 or 2025/26 outcomes. This
document is a plan for S05, nothing more.

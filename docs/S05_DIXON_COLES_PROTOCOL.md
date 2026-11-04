# S05 Dixon-Coles protocol — frozen before fitting or viewing any challenger result

Every numeric default and implementation choice below is fixed here, BEFORE
`dixon_coles_team_poisson` was fitted against any held-out fixture and BEFORE any S05 result
was inspected. None of these constants were tuned against the 760 evaluated fixtures. This is
the single, pre-registered challenger for S05 — not a menu of variants to pick the best from in
hindsight.

## What this challenger is, precisely

`dixon_coles_team_poisson` reuses the frozen `team_goal_poisson`'s exact pre-match
`lambda_home`/`lambda_away` for each fixture (same k=5 shrinkage, same league means, same
training data) — nothing about how those two numbers are computed changes. On top of that
pair, it introduces exactly **one** new scalar, `rho`, applied only to four low-scoring joint
outcomes, via the classic Dixon & Coles (1997) multiplier:

```
tau(0,0) = 1 - lambda_home * lambda_away * rho
tau(1,0) = 1 + lambda_away * rho
tau(0,1) = 1 + lambda_home * rho
tau(1,1) = 1 - rho
tau(i,j) = 1                           for every other (i, j)
```

No decay half-life, no Elo, no learned home advantage, no hyperparameter search, no goal-rate
refitting. `rho = 0` recovers `team_goal_poisson`'s existing 1X2 probabilities to numerical
tolerance, by construction (every `tau` term equals 1 when `rho = 0`) — this is a hard
regression check, not an aspiration.

## Joint-grid construction, normalisation, and failure mode

The DC correction is applied to the **joint goal-count grid**, BEFORE aggregating into H/D/A —
never to an already-aggregated 1X2 vector (applying it afterwards would not correspond to any
real joint distribution). Concretely: reuse the existing goal-grid construction (same tail-bound
search, same `POISSON_TAIL_BOUND = 1e-10`, same `POISSON_MAX_GOALS_CAP = 100` as
`team_goal_poisson`) to get the independent Poisson joint masses `P(i)·P(j)` over the grid
`i, j <= M`; multiply the four low-score cells by their `tau` value; **renormalise the full
adjusted grid** so it sums to 1 before aggregating into H/D/A (the un-adjusted grid's tail mass
is retained as a diagnostic, exactly as `team_goal_poisson` already does).

**Fail closed, never clip:** if any adjusted joint mass over the four low-score cells would be
negative or non-positive for the fitted/candidate `rho`, this is an error — never silently
clipped to zero. The bound-computation step below exists specifically to prevent this from
happening at evaluation time; the implementation still checks it explicitly and raises
`DixonColesError` if it ever occurs, rather than trusting the bound computation alone.

## rho estimation protocol — walk-forward, prequential, no leakage

**Primary fitting choice (frozen):** at each unique evaluation date `d`, `rho` is re-estimated
from scratch using only matches with `match_date < d` (via
`chronology.completed_training_results_as_of`, identical same-day-batch exclusion rule as every
other model in this project). The **same fitted `rho` is reused for every fixture evaluated on
that date** — it is a single scalar per date, not a per-fixture parameter.

**Prequential (no target-score leakage) requirement:** for EVERY training match used in the
`rho` objective, its own pre-match `lambda_home`/`lambda_away` are computed from results
STRICTLY before THAT match's own date — never from data that includes that match itself or
anything after it. This means fitting `rho` for evaluation date `d` requires, in principle, a
full walk-forward lambda computation for every one of the (up to ~1140) training matches that
occurred before `d`.

**Caching (frozen implementation choice, not a shortcut):** a training match's own pre-match
`(lambda_home, lambda_away)` pair depends ONLY on that match's own date and the results strictly
before it — it does NOT depend on which later evaluation date `d` is currently being predicted.
This project therefore computes each of the (up to 1140) scored matches' pre-match lambda pair
**exactly once**, in a single pass over the eligible historical corpus sorted by date, and reuses
that cached value for every later evaluation date's `rho` fit that includes that match as a
training observation. This is a correctness-preserving cache, not an approximation: it produces
the identical result a naive re-computation would, just without repeating identical work.

**Objective:** maximise `sum(log(tau(observed_i, observed_j; lambda_home, lambda_away, rho)))`
over the eligible training observations at date `d` (the independent-Poisson log-likelihood
terms are constant in `rho` and are correctly omitted — including them would not change where
the maximum is). In practice only the training matches whose own final score is one of the four
low-score cells contribute a non-zero term (every other match contributes `log(1) = 0`
regardless of `rho`); both are mathematically identical, so the implementation may restrict the
sum to those matches for efficiency.

**Insufficient-history fallback (frozen, not an invented estimate):** if fewer than **50**
completed matches exist before date `d` (regardless of their scoreline), `rho` is set to
exactly `0.0` and `fit_status = "insufficient_history"` — never an optimised value computed from
too little data, and never silently indistinguishable from a genuine zero-correlation fit.

## Bounds — frozen, computed only from training-and-current pre-match data, never from outcomes

**Outer range (frozen):** `[-0.20, +0.20]`.

**Analytical positivity intersection (frozen):** for every `(lambda_home, lambda_away)` pair that
will actually be evaluated against a `tau` term at date `d` — every training observation's
cached pre-match pair, AND the current fixture's own pre-match pair — compute the sub-range of
`rho` that keeps all four `tau` values `> POSITIVITY_MARGIN = 1e-12`:

```
tau(0,0) > margin  =>  rho <  (1 - margin) / (lambda_home * lambda_away)
tau(1,1) > margin  =>  rho <  1 - margin
tau(1,0) > margin  =>  rho > -(1 - margin) / lambda_away
tau(0,1) > margin  =>  rho > -(1 - margin) / lambda_home
```

giving a per-pair valid interval `[max(the two lower bounds), min(the two upper bounds)]`. The
final bound for date `d` is the intersection of the outer range with EVERY per-pair interval
(training observations and the current fixture alike) — never computed from, or widened by,
the current or any future fixture's actual result. `rho = 0` always lies strictly inside every
individual per-pair interval (since all four `tau` values equal exactly 1 there), so the
intersection is mathematically guaranteed to contain 0 and cannot become empty in any
non-degenerate case; the implementation still checks this explicitly and raises
`DixonColesError` rather than silently proceeding if it somehow does.

**Boundary disclosure (frozen):** if the optimised `rho` lands within `1e-6` of either bound,
`fit_status` is recorded as `"boundary_low"` or `"boundary_high"` instead of `"fitted_interior"`
— this is disclosed in the audit trail, never silently treated as an ordinary interior fit.

## Optimiser — frozen

Deterministic, bounded, **golden-section search** (unimodal/concave objective — a sum of
`log(linear-in-rho)` terms is concave wherever all four `tau` values are positive, which the
bound computation above already guarantees): maximum **120** iterations, parameter convergence
tolerance **1e-8**. No random seed is used or needed — golden-section search is fully
deterministic given its bounds and objective.

## Leakage discipline — explicit, testable claims

- A mutation to a target evaluation date's OWN result, or to any result dated on or after it,
  must change neither that date's fitted `rho` nor any prediction on that date — because neither
  ever enters `completed_training_results_as_of(records, d)` for that `d`.
- A mutation to a genuinely EARLIER result (one that is itself used as a training observation,
  either in the `rho` fit or in some later match's cached pre-match lambda) CAN change `rho`
  and the resulting predictions — this is the required positive control, proving the leakage
  control is discriminating, not simply inert.
- Promoted/cold-start teams use the existing, unmodified k=5 pseudo-match shrinkage for their
  `lambda_home`/`lambda_away` — no second, team-specific `rho` or any other new per-team
  parameter is introduced.

## Candidate selection — frozen before results exist

This is the ONE challenger evaluated in S05. There is no menu of alternative `rho`
parameterisations, decay schemes, or bound choices being compared to pick a winner after seeing
scores. If `dixon_coles_team_poisson` does not beat frozen `team_goal_poisson` on log loss, the
documented conclusion is that this specific, pre-registered complexity increase did not earn
adoption in this replay — not a prompt to retune, redefine, or try a second variant.

## Hindsight disclosure (restated from `docs/S04_CHALLENGER_RESEARCH_PLAN.md`)

Both 2024/25 and 2025/26 outcomes have already been inspected repeatedly across S03/S04/S05.
Chronological as-of discipline (`completed_training_results_as_of`, applied identically to the
`rho` fit) prevents any MODEL from using future information relative to its own prediction
date — it does not make this a blind, prospective test for the humans who already know which
fixtures were surprising and where the draw gap showed up. Every S05 result is reported as an
**exploratory, hindsight-informed chronological replay**, not a pristine holdout, in both the
result document and this protocol.

## Addendum — discovered during implementation, frozen before any result was fitted

Building the prequential lambda cache (above) surfaced a genuine edge case this protocol had
not anticipated: `team_goal_poisson`'s own existing validation (unchanged, not weakened here)
requires `league_home_mean > 0` and `league_away_mean > 0` over the training set used to compute
a match's lambda pair. For the first handful of matches in the 2023/24 season — training sets of
size 1–2 — the league-wide mean can be EXACTLY zero (e.g. the very first match's training set is
just the single opening fixture, and if that match's home team scored 0 goals, the league home
mean over that one-match "league" is exactly 0.0). This is not a bug in the validation; it is a
genuine case where that early match's own training history is too sparse to support ANY valid
pre-match lambda pair, by the same rule `team_goal_poisson` has always enforced.

**Frozen resolution:** when a corpus match's own prequential lambda pair cannot be computed
(the existing `BaselineModelError` validation fails), that match is simply **excluded from the
prequential cache** and therefore never contributes a training observation to any later date's
`rho` fit — it is never assigned an invented or fallback lambda pair at this stage. This affects
only a small number of the earliest 2023/24 matches (verified: by the time the training set
reaches double digits, the league mean is never exactly zero in the real corpus); it has zero
effect on the CURRENT fixture being predicted on any evaluation date (2024/25 or 2025/26), whose
own lambda is always computed fresh from that date's full training set (hundreds of matches,
never degenerate in practice) exactly as `team_goal_poisson` already does. This is a cache-input
availability rule, not a change to any `rho`-fitting formula, bound, or constant above.

## What is explicitly out of scope for S05

No decay half-life, no Elo rating, no learned home-advantage term, no second challenger
variant, no hyperparameter search of any kind, no 2026/27 data, no change to
`live_claim_allowed` (remains hard-coded `False`), no public product implementation.

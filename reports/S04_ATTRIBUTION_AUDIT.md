# S04 attribution audit — how much of the Poisson gain is "team identity"?

Entirely historical. Nothing here is a live forecast. Full numbers:
`reports/s04_attribution_metrics.json`. Per-fixture audit (not tracked in Git):
`data/processed/s04_ablation_predictions_REVIEW.csv` (3,040 rows = 760 fixtures × 4 models).
S03's original three-model outputs (`reports/s03_baseline_backtest_metrics.json`,
`data/processed/s03_backtest_predictions_REVIEW.csv`) are **unchanged** — confirmed
byte-identical before and after this slice's every code change.

## The question

S03 found `team_goal_poisson` beats the categorical `expanding_league_prior` (log loss 1.0147
vs. 1.0833). But that comparison changes BOTH the use of team identity AND the likelihood
family (categorical outcome distribution vs. independent-Poisson goal model) at once. It was
not, by itself, proof the improvement comes from team identity. `league_only_poisson` isolates
this: identical Poisson machinery (same `_poisson_outcome_distribution` grid/tail-bound/
aggregation routine, same tail bound, same safe empty-training fallback), but
`lambda_home`/`lambda_away` are the plain league-wide goal means — no team identity read at
all.

## Result: within this comparison path, the step that matters is adding team identity

| Model | Log loss (overall, N=760) |
| --- | --- |
| Expanding league prior | 1.0833 |
| **League-only Poisson (no team identity)** | **1.0817** |
| **Team-goal Poisson (with team identity)** | **1.0147** |

`league_only_poisson` is barely different from `expanding_league_prior` — switching to a
Poisson/goal-based likelihood family **by itself**, with no team-specific information, buys
almost nothing. The real improvement comes from adding team-specific attack/defence rates on
top of that likelihood family.

### Decomposition (paired date-block bootstrap, seed=20250103, 1000 replicates per comparison)

| Step | Overall log-loss diff | 95% descriptive interval |
| --- | --- | --- |
| League-only Poisson − Expanding prior (**Poisson-family-alone effect**) | **−0.0016** | [−0.0030, −0.0001] |
| Team-goal Poisson − League-only Poisson (**team-identity effect**) | **−0.0669** | [−0.0915, −0.0417] |
| **Sum (≈ S03's total team-goal − expanding result)** | **−0.0685** | (S03: −0.0685, [−0.0929, −0.0434]) |

The two component intervals both exclude zero, but the team-identity step is roughly
**40× larger** than the Poisson-family-alone step in this specific decomposition.

**Correction (S05) — tightened wording, same numbers:** within this particular *sequential
model comparison / accounting bridge* (expanding prior → league-only Poisson → team-goal
Poisson, in that order), about 98% of the observed ~0.0685 log-loss improvement falls on the
league-only-Poisson → team-specific-Poisson step, and about 2% falls on the expanding-prior →
league-only-Poisson step. **This is a path-dependent accounting split across three specific
models, not a causal or factorial identification of "how much of the improvement is caused by
team identity" in any model-agnostic sense, and not a universal percentage that would hold
under a different comparison path, baseline ordering, or model set.** A different sequence of
models (e.g. comparing team-goal Poisson directly against a team-aware categorical baseline
that doesn't yet exist) could attribute the same total improvement differently. The numbers
themselves (−0.0016, −0.0669, −0.0685) are unchanged — only the word "attributable" has been
replaced with language that doesn't imply more than a three-model accounting bridge supports.

### Per-season consistency

| Season | Poisson-family-alone diff | Team-identity diff |
| --- | --- | --- |
| 2024/25 | −0.0024 [−0.0045, −0.0003] | −0.0827 [−0.1196, −0.0459] |
| 2025/26 | −0.0007 [−0.0027, +0.0011] | −0.0512 [−0.0875, −0.0130] |

The team-identity effect is unambiguous (interval entirely negative) in both seasons
individually. The Poisson-family-alone effect is unambiguous in 2024/25 but its 2025/26
interval includes zero — consistent with it being a genuinely small effect that is harder to
resolve at N=380 per season.

## What this does and does not establish

- **Does establish:** within this specific three-model sequential comparison, the
  league-only-Poisson → team-specific-Poisson step accounts for the large majority of
  `team_goal_poisson`'s real, out-of-time log-loss advantage over the categorical baseline —
  far more of it than the expanding-prior → league-only-Poisson step. This is a genuine,
  verified result about THIS comparison path, not an assumption restated.
- **Does not establish:** a causal or factorial identification of "how much of the improvement
  team identity causes" in a model-agnostic sense, a universal percentage that would survive a
  different comparison path or baseline ordering, or that a Poisson/goal-based likelihood is
  never useful on its own in any other context, league, or time window — this is one specific
  ablation, compared one specific way, on one specific corpus. It also does not establish a
  formal statistical significance claim; the bootstrap intervals are descriptive and
  approximate, stated as such throughout.
- **Does not change** any S03 figure. S03's `team_goal_poisson` vs. `expanding_league_prior`
  comparison is correct as originally reported; this audit only adds the missing middle term
  of the decomposition.

## Shared-machinery proof (not just an assertion)

`baseline_models._poisson_outcome_distribution(lambda_home, lambda_away)` is the single,
frozen goal-grid/tail-bound/outcome-aggregation routine both Poisson models call — there is no
second, divergently-maintained copy of this calculation. Verified directly by test
(`tests/test_baseline_models.py::test_c_team_goal_and_league_only_poisson_agree_on_a_fully_symmetric_training_set`
and the companion cold-start test): on a training set where every team's rates are identical
(or where both fixture teams have zero history), `team_goal_poisson` and `league_only_poisson`
produce byte-identical output — exactly what sharing one routine predicts, and what a second,
subtly different implementation could easily have failed.

## No tuning performed

`POISSON_SHRINKAGE_K` (5), the goal-grid tail bound (1e-10), the safe empty-training fallback
(1.5/1.5), and every S03 baseline constant are unchanged. `league_only_poisson` introduces no
new free parameter — it reuses every existing constant and the existing fallback, never
retuned against this or any held-out result.

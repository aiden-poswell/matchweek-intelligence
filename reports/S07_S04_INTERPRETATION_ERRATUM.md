# S07 erratum — S04 bootstrap sign-interpretation string, corrected

## What was wrong

`src/matchweek_intelligence/build_attribution_backtest.py::_date_block_bootstrap_log_loss_diff`
computes `point_diff = mean(log_loss(model_right)) - mean(log_loss(model_left))` and
stores it as `point_diff_log_loss_right_minus_left`. A **negative** value therefore
means `model_right`'s log loss is **lower** (better) — `model_right` wins. The
function's returned `"interpretation"` field, and its own docstring, said the
opposite: **"negative means left_model wins (lower log loss)."** This was backwards.

This is the exact same class of bug independently found and fixed for the S05/S06
challenger report (`build_challenger_backtest.py`) in S06 Stage A1. At the time, S06
deliberately left **this** file's identical copy of the bug unfixed, because fixing
it then would have silently altered the already-committed, frozen S04 artifact
(`reports/s04_attribution_metrics.json`) without a dedicated erratum — a line this
project holds firmly ("never silently touch frozen historical outputs"). S06's
findings document disclosed this explicitly as a known, deferred defect. **S07 is
that dedicated erratum.**

## Reproduction (before fixing)

A synthetic pair with exact, known log losses (`worse_model` constant 2.0,
`better_model` constant 1.0, 60 shared dates):

```
point_diff_log_loss_right_minus_left: -1.0
interpretation (as originally written): negative means left_model wins (lower log loss)
left_model: worse_model   right_model: better_model
```

`better_model` (the right model, log loss 1.0) is unambiguously the true winner —
confirmed by construction. The original string claimed the opposite (`worse_model`,
the left model) wins when the diff is negative. The bug was real and reproduced
before any fix was applied, exactly as required.

## The fix

- The `interpretation` string now reads **"negative means right_model wins (lower
  log loss)"**.
- The function's docstring was corrected to match.
- A new regression test,
  `tests/test_build_attribution_backtest.py::test_s07_bootstrap_interpretation_matches_the_actual_sign_direction_both_ways`,
  proves **both** directions explicitly: the synthetic pair above with `right_model`
  winning (diff negative), and the same pair with `left_model`/`right_model` swapped,
  where `left_model` now wins (diff positive) — confirming the sign convention is
  symmetric and correctly labelled either way, not merely correct for one
  cherry-picked case.

## Regenerating the S04 artifact — numeric-deep-equality verification

`reports/s04_attribution_metrics.json` was regenerated from the real pinned-commit
cache via the unchanged canonical pipeline
(`uv run python -m matchweek_intelligence.build_attribution_backtest`).

```
expanding_league_prior: log_loss=1.0833 brier=0.6563 rps=0.2317
rolling_league_frequency: log_loss=1.0943 brier=0.6631 rps=0.2342
team_goal_poisson: log_loss=1.0147 brier=0.6078 rps=0.2081
league_only_poisson: log_loss=1.0817 brier=0.6553 rps=0.2314
team_goal_poisson - league_only_poisson (overall log-loss diff): -0.0669
```

These match the S04/S05 anchors exactly (same as reported throughout S04, S05, and
S06). A recursive, numeric-deep-equality comparison of the full regenerated JSON
tree against the pre-erratum file found:

- **0 numeric differences** anywhere in the document (every log loss, Brier, RPS,
  accuracy, bootstrap point-diff, confidence-interval bound, and config constant is
  bit-for-bit identical).
- **Exactly 6 string differences**, all and only the `"interpretation"` field at
  every occurrence (3 comparisons × {overall, 2024-25, 2025-26} = 6 scopes).

| File | SHA-256 |
| --- | --- |
| `reports/s04_attribution_metrics.json` — before this erratum | `ac3a8ae79ade99fa484131f35c998968ee79f7dca391071708458724219623a4` |
| `reports/s04_attribution_metrics.json` — after this erratum | `23da780dcd9430c3d6e6ecf192a333f6b6a13b3cbaa77f359aa17ef56b5fedb2` |

The "before" hash matches the hash recorded at the end of every prior slice's
verification document (S04 through S06) — confirming this file had not drifted at
all until this deliberate, disclosed, six-string correction.

## Re-verification of everything else — zero new drift

Re-checked immediately after regenerating the S04 artifact:

| Artifact | Result |
| --- | --- |
| `reports/s03_baseline_backtest_metrics.json` | byte-identical |
| `data/processed/s03_backtest_predictions_REVIEW.csv` | byte-identical |
| `data/processed/s04_ablation_predictions_REVIEW.csv` | byte-identical |
| `reports/s04_calibration_diagnostics.json` | byte-identical |
| `reports/s05_challenger_metrics.json` | unchanged from S06 — still differs from its own pre-S06 baseline in only the 3 strings S06 Stage A1 already sanctioned and documented; **no new S07 drift** |
| `data/processed/s05_challenger_predictions_REVIEW.csv` | byte-identical |
| `reports/s05_rho_fit_audit.json` | byte-identical |
| `web/public/data/replays.json` | byte-identical — SHA-256 `746eabc9f24e87f48b220661058e81b698857b6719e36a5756490f6c65d5328c`, the exact hash independently verified in the S06 review |

No other file changed as a result of this erratum.

## Why this is a transparent correction, not a covert rewrite

- The fix is **disclosed here, by name, with before/after hashes**, not silently
  folded into a routine regeneration.
- It corrects a **machine-readable label**, not any model, score, probability, or
  evaluation result. Every number in `reports/s04_attribution_metrics.json` — the
  actual evidence about model performance — is byte-identical to before.
- The written prose conclusions in `reports/S04_ATTRIBUTION_AUDIT.md` were already
  consistent with the correct (right-wins-when-negative) direction; only the JSON
  field itself was wrong, exactly mirroring the S06 Stage A1 finding for the sibling
  file.
- This erratum does **not** retroactively claim the S04 report "always said" the
  correct thing — it states plainly that it did not, for how long (S04 through S06),
  and why the fix was deferred until now.
- No historical fact about when S04 was computed or committed is altered or
  reinterpreted. The S05 provenance correction
  (`reports/S06_PROVENANCE_CORRECTION.md`) remains the accurate account of that
  separate issue and is not revisited or weakened by this erratum.

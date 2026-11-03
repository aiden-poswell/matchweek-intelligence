# S04 calibration and failure diagnostics

Entirely historical, retrospective. All figures below were computed directly from the 3,040-row
S04 prediction export (`run_attribution_backtest` → `build_calibration_diagnostics.build_report`)
and written to `reports/s04_calibration_diagnostics.json` — none are hand-entered. Every
number here was independently re-derived from the raw CSV probability/outcome columns using a
standalone recalculation that imports neither `metrics.py` nor `build_attribution_backtest.py`'s
own aggregation helpers (max absolute difference against the tracked JSON: ~2×10⁻¹⁵, see
`matchweek-intelligence-s04-verification.md`).

## 1. Mean predicted vs. observed outcome frequency (all four models, N=760 overall)

| Model | Outcome | Predicted % | Observed % | Gap (obs − pred, pp) |
| --- | --- | --- | --- | --- |
| Expanding league prior | D | 23.23 | 25.92 | **+2.69** |
| Rolling league frequency | D | 25.28 | 25.92 | **+0.64** |
| Team-goal Poisson | D | 22.38 | 25.92 | **+3.54** |
| League-only Poisson | D | 23.63 | 25.92 | **+2.29** |

**All four models under-predict draws.** This is not unique to the Poisson model, but
`team_goal_poisson` has the LARGEST draw-calibration gap of the four, despite having the best
overall log loss — a real, slightly counter-intuitive finding, stated plainly rather than
smoothed over. `rolling_league_frequency` has the smallest gap, which makes direct sense: it
estimates the draw rate as a literal recent empirical frequency, with no goal-count model in
between to introduce independence-assumption error.

**Independent S03 anchor confirmation (team_goal_poisson):** overall 22.3843% predicted vs.
25.9211% observed, gap +3.5368pp; 2024/25: 21.89% vs. 24.47% (+2.59pp); 2025/26: 22.88% vs.
27.37% (+4.49pp) — all four figures match the brief's independently-recalculated anchors
exactly (within the stated rounding), confirmed directly against
`reports/s04_calibration_diagnostics.json`, not re-asserted from memory.

Full H/D/A mean-predicted-vs-observed tables for all four models, overall and per season, are
in `reports/s04_calibration_diagnostics.json` under `mean_vs_observed` — H and A both show the
complementary, smaller-magnitude over-prediction (home win over-predicted ~3pp, away win
roughly balanced), consistent with the three outcome probabilities summing to 100% on both the
predicted and observed side.

## 2. Equal-count calibration bins (5 bins, team_goal_poisson, draw outcome)

Deterministic bins: sort all 760 fixtures by predicted P(draw), tie-break on the immutable
`(match_date, home_team, away_team)` key, split into 5 equal-count bins (152 fixtures each).

| Bin | N | Predicted P(D) range | Mean predicted % | Observed rate % |
| --- | --- | --- | --- | --- |
| 0 | 152 | 0.089 – 0.194 | 17.06 | 17.76 |
| 1 | 152 | 0.194 – 0.220 | 20.87 | 26.97 |
| 2 | 152 | 0.220 – 0.236 | 22.81 | 28.29 |
| 3 | 152 | 0.236 – 0.253 | 24.35 | 23.03 |
| 4 | 152 | 0.253 – 0.305 | 26.82 | 33.55 |

No monotonically increasing miscalibration pattern across bins (bin 3's observed rate is
actually below its predicted rate) — the draw under-prediction is a real net effect across the
full sample, not a simple "always under by a fixed amount at every probability level" pattern.
N=152 per bin supports this level of granularity; a finer binning would not be well-supported
by only 760 fixtures. Full bins for all four models × three outcomes are in the JSON
(`equal_count_bins`) — not reproduced here in full to avoid implying a precision the sample
doesn't support everywhere.

**This is a descriptive bin table, not a calibration chart, and is not claimed to be "a
calibrated forecast."** Every number has its N stated; no visual implies finer resolution than
152-fixture bins can actually support.

## 3. Log-loss breakdowns (descriptive checks only)

### By evaluated season

| Model | 2024/25 (N=380) | 2025/26 (N=380) |
| --- | --- | --- |
| Expanding league prior | 1.0823 | 1.0842 |
| Rolling league frequency | 1.0977 | 1.0910 |
| Team-goal Poisson | **0.9972** | **1.0323** |
| League-only Poisson | 1.0799 | 1.0835 |

Team-goal Poisson's advantage is larger in 2024/25 than 2025/26 (consistent with S03's original
finding); league-only Poisson tracks the expanding prior closely in both seasons, reinforcing
the attribution result in `reports/S04_ATTRIBUTION_AUDIT.md`.

### By predicted favourite strength (max(P(H),P(D),P(A)) band)

For `team_goal_poisson`: no fixture had a favourite below 33% (N=0, that band is empty and
reported as such, not silently omitted); 0.33–0.45 band N=246, mean log loss 1.083; 0.45–0.55
band N=223, mean log loss 1.104; >0.55 band N=291, mean log loss 0.889. The model scores best
when it is most confident, as expected for a working model — not treated as evidence of
superiority beyond this specific sample.

### Cold-start subset (N=5 — descriptive only, no generalisation)

| Model | Cold-start mean log loss (N=5) | Warm mean log loss (N=755) |
| --- | --- | --- |
| Expanding league prior | 1.023 | 1.084 |
| Rolling league frequency | 1.024 | 1.095 |
| Team-goal Poisson | **0.821** | 1.016 |
| League-only Poisson | 1.022 | 1.082 |

Team-goal Poisson's 5 cold-start fixtures score noticeably better than its own warm-fixture
average, unlike the other three models (whose cold-start/warm gap is much smaller). **This is
explicitly NOT generalised into any claim about the model handling promotions well** — N=5 is
far too small to support that, and it could easily be a sampling artefact of which five
specific matches happened to be cold-start cases (see `reports/S03_BASELINE_BACKTEST.md`'s
list: Ipswich Town, Leicester City, Sunderland, Leeds United, Southampton). Reported because it
is visible in the data, not because it is a conclusion.

### A note on the draw under-prediction's possible causes (not distinguishable here)

The evidence in this report cannot tell apart at least three plausible explanations for the
draw gap: (1) the independent-Poisson assumption genuinely under-weights low-scoring,
correlated outcomes (the textbook Dixon-Coles motivation); (2) league-wide draw base rates
may simply be higher in 2024/25-2025/26 than the broader historical pattern the model's
shrinkage implicitly assumes; (3) ordinary sampling variation at N=760. Distinguishing these
requires a controlled challenger (see `docs/S04_CHALLENGER_RESEARCH_PLAN.md`), not a re-read of
the same numbers.

## 4. Failure analysis — most surprising fixtures (team_goal_poisson, by log loss)

All from the real, CC0-licensed `openfootball/england` pinned source already cleared for this
project (`docs/SOURCE_RIGHTS_AND_PROVENANCE.md`) — these are retrospective historical examples,
not live forecasts, and are the SAME source data used throughout this project, not a new
disclosure.

| Date | Fixture | Score | Model's pre-match view | Actual | Log loss |
| --- | --- | --- | --- | --- | --- |
| 2025-02-22 | Arsenal v West Ham United | 0–1 | P(H)=78.0%, P(D)=13.4%, P(A)=8.6% | Away win | 2.458 |
| 2025-05-10 | Southampton v Manchester City | 0–0 | P(H)=4.5%, P(D)=9.6%, P(A)=85.9% | Draw | 2.339 |
| 2024-09-14 | Liverpool v Nottingham Forest | 0–1 | P(H)=74.2%, P(D)=15.8%, P(A)=10.0% | Away win | 2.302 |
| 2025-11-22 | Liverpool v Nottingham Forest | 0–3 | P(H)=71.4%, P(D)=16.9%, P(A)=11.8% | Away win | 2.141 |
| 2026-03-22 | Newcastle United v Sunderland | 1–2 | P(H)=67.4%, P(D)=20.5%, P(A)=12.1% | Away win | 2.111 |

No injuries, formations, tactics, or narrative explanation is offered for any of these — this
source has no such data, and inventing one would not be grounded in evidence. These are simply
the fixtures where a heavily favoured team lost or drew against long odds, which is exactly
what "surprising, by this model's own pre-match view" means. Full per-fixture detail for all 760
fixtures × 4 models remains in the separate, gitignored
`data/processed/s04_ablation_predictions_REVIEW.csv`.

## 5. Independent recalculation and integrity checks

A standalone script (no import of `metrics.py` or `build_attribution_backtest.py`'s own
aggregation) re-read `data/processed/s04_ablation_predictions_REVIEW.csv` and re-derived
log-loss/Brier/RPS directly from `p_home`/`p_draw`/`p_away`/`actual_outcome` for every
model × season × scope, checking against `reports/s04_attribution_metrics.json`:

- **Maximum absolute difference: ~2×10⁻¹⁵** (well inside the required 1e-10 tolerance).
- All four models: exactly 760 unique `(match_date, home_team, away_team)` keys, exactly
  380/380 season split, zero duplicates.
- Every probability triple strictly positive and summing to 1 within 1e-9.
- Every `latest_training_match_date` strictly precedes its fixture's `match_date` (string-ISO
  comparison, confirmed for all 3,040 rows — zero violations).
- No row anywhere has `season == "2026-27"`.

`build_calibration_diagnostics.build_report()` re-runs every one of these checks itself before
writing anything (`_validate_integrity`), raising `CalibrationDiagnosticsError` and writing no
output on any violation — proven directly by
`tests/test_build_calibration_diagnostics.py::test_build_report_fails_closed_before_writing_if_integrity_is_violated`.

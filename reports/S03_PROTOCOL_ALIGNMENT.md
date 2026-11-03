# S03 protocol alignment — before/after normative corrections

Stage A of S03 required repairing stale normative references (instructions, not historical
findings) before any model was fitted. This report records exactly what changed and why, and
is itself evidence that the correction happened — it should be read alongside the actual diffs
in `README.md`, `docs/FORECASTING_PROTOCOL.md`, and `docs/SOURCE_RIGHTS_AND_PROVENANCE.md`.

## 1. README.md

**Before:** "Status: Slice 01 — data feasibility only," describing only the S01 audit as
built and listing "no model, no forecast" as blanket facts.

**After:** States S01/S02 as completed, S03 as in-progress with its actual scope (three
predeclared baselines, backtest, no live claim). Explicitly separates "what is built" from
"what is explicitly NOT built yet" (public product, sophisticated challenger, any live/current
forecast).

**Why:** The repository had materially progressed past "data feasibility only"; leaving that
line in place would have been a normatively false status claim, not merely out of date prose.

## 2. docs/FORECASTING_PROTOCOL.md

**Before (a):** Header claimed "No model is fitted... as of Slice 01" with no update path.

**After (a):** Header now states S03 implements exactly the three baselines in the
"Baselines" section, points to `docs/S03_BASELINE_METHODS.md` for frozen constants and
`reports/S03_BASELINE_BACKTEST.md` for the result, and clarifies the "candidate models"/"public
product" sections remain unimplemented.

**Why:** The original header was a point-in-time snapshot written before any slice after S01
existed; left unedited, it actively misdescribes the repository's current state to a reader who
opens this file after S03.

**Before (b):** "Same-day fixtures are always a simultaneous batch (`chronology.as_of_filter`)"
— presented as if `as_of_filter` were the correct model-training input.

**After (b):** Names `chronology.completed_training_results_as_of(records, cutoff_date)` as the
only training-safe helper, explains `as_of_filter` is status-agnostic and can still return a
`result_missing` row, and links to `docs/DATA_CONTRACT.md` for the full two-helper contract.

**Why:** This is the single most dangerous stale reference in the document — the brief's
reviewer flagged it specifically ("suggests using status-agnostic chronology.as_of_filter as
the model input"). Following the original wording, as written, is close to the most direct path
to a real leakage bug: a current-season `result_missing` row dated before a cutoff would pass
`as_of_filter` and could silently enter a training set.

**Before (c):** "gated on the current-season source passing its own freshness check
(`current_season_publishable = true`)."

**After (c):** Replaced with the actual S02 gate name, `live_claim_allowed = True`, with an
explicit statement that it is hard-coded `False` in `build_data_quality.py` and that nothing in
this repository can currently set it `True`.

**Why:** `current_season_publishable` no longer exists as a field; a reader implementing the
eventual public product against this document would be checking a field that is not there.

**Before (d):** Stop condition referencing "`result_missing` rows that can't be bounded by
`as_of_filter`" — the same status-agnostic helper named as if it were the safety mechanism.

**After (d):** Restated around `completed_training_results_as_of`, whose status filter makes a
`result_missing` row reaching it a structural impossibility by construction, not something that
needs to be "bounded."

**Why:** Same root cause as (b); a stop condition phrased around the wrong helper is not a real
safety net.

**Before (e):** Baseline #3 described the goal-rate Poisson model as "no decay, no
regularisation."

**After (e):** Corrected to state that an unregularised MLE goal rate is undefined or wildly
unstable for a promoted club with little or no prior top-flight history — a real, recurring
situation in this corpus (every eligible season has promoted clubs) — and that S03
pre-registers a fixed k=5 pseudo-match shrinkage toward the contemporaneous league goal mean as
a necessary baseline adjustment, frozen in `docs/S03_BASELINE_METHODS.md` and never tuned
against the held-out seasons.

**Why:** This is the exact tension the brief named: "S01's proposed unregularised team-rate
Poisson is incompatible with cold-start teams and zero-history teams." Shipping a model that
literally has no regularisation would either crash (division by zero for a team with zero
training matches) or produce an unbounded/garbage goal rate for a team with one or two matches.
Calling the shrunk version "no regularisation" would have been a false claim about the model
actually implemented in Stage C.

## 3. docs/SOURCE_RIGHTS_AND_PROVENANCE.md

**Before:** Sections 1d/1f state "`current_season_publishable` for this file: False" and "###
1f. `current_season_publishable` status" as live, current field references.

**After:** Both sections are annotated **in place**, not rewritten or deleted — the original
2026-11-02 evidence and conclusion (2026/27 blocked; the specific fixture counts and staleness
figures) are preserved exactly as found. An added note explains the field name was retired in
S02 for the reason already documented in §1d (the reproduced fail-open defect), and that the
historical conclusion is unaffected and now expressed via `historical_season_complete` /
`current_results_coverage_sufficient` / `live_claim_allowed`.

**Why:** The brief was explicit: "Identify these as S01-era historical conclusions under a
retired gate, then link the S02 replacement fields. Do not simply delete the audit trail or
change source evidence." Deleting or silently rewording a dated audit finding would itself be a
worse integrity problem than leaving a retired field name temporarily unexplained — the fix is
annotation, not erasure.

## 4. The 2027-01-01 vs. 2026-11-02 distinction (restated explicitly, not just cross-referenced)

`reports/s02_historical_corpus_quality.json` uses a **fixed analytical constant**,
`corpus_as_of_date = 2027-01-01`, chosen only to be safely past every historical season's own
declared end date, so that season-completeness checks (`historical_season_complete`) are
evaluated meaningfully. `reports/s01_data_quality.json` uses the **real current date**,
2026-11-02, as its as-of basis — it is the authoritative "as of now" freshness view.

These two reports necessarily disagree on 2026/27's scored/missing/future counts (the corpus
report evaluates far more of that season as "in the past" than is actually true today). This is
correct, not a bug, and is restated here explicitly because S03's backtest evaluation schedule
depends on genuinely understanding which constant means what: **the 2027-01-01 sentinel is an
audit convention for checking season completeness, never a license to train or evaluate on any
result that would require 2026/27 to have actually reached that date.** S03's backtest never
uses 2026/27 at all, in training or evaluation, regardless of either as-of date.

## 5. Regression tests added

`tests/test_protocol_hygiene.py` scans the four normative docs
(`README.md`, `docs/FORECASTING_PROTOCOL.md`, `docs/SOURCE_RIGHTS_AND_PROVENANCE.md`,
`docs/BACKTEST_INPUT_CONTRACT.md`) for the retired field name `current_season_publishable`
appearing WITHOUT a nearby retirement/historical-context marker (`S01-era`, `retired`, `S02
note`, `no longer`), and for any remaining prescriptive use of `as_of_filter` as if it were the
correct model-training input. It explicitly does NOT fail on the two annotated historical
mentions left in `docs/SOURCE_RIGHTS_AND_PROVENANCE.md` — those are accurate historical record,
not stale instruction, and the test asserts the annotation is present rather than asserting the
old name's total absence.

# S05 public product brief — the Matchweek Replay Lab (plan only, nothing built)

Status: this is a specification for a **future slice**. No website, UI, or application code is
implemented in S05 or by this document. It exists so the next slice has a concrete, decided
brief to build against, grounded in the actual S03–S05 research findings — not a generic
"AI sports dashboard" concept.

## What it is

A small, historical, honestly-labelled web page: **the Matchweek Replay Lab.** A visitor picks
a real, completed Premier League fixture from 2024/25 or 2025/26, and sees exactly what this
project's frozen model would have said about it **using results from before this match date**
— alongside the actual result, and the model's season-level track record. **Correction (S06):**
the modelling pipeline works at match-date granularity, not a validated precise kickoff
timestamp with timezone, and it excludes all matches on the target date from training — so the
product must never say "before kickoff," "available at kickoff," or any other falsely precise
intraday statement. Every forecast was computed retrospectively on historical results; none
could have been publicly issued in advance. It is a demonstration of disciplined, leak-free,
chronologically honest forecasting methodology, not a prediction service.

## What it is not

- **Not** a live or current forecasting product. There is no 2026/27 prediction anywhere, and
  none is planned — the source remains stale and blocked (`live_claim_allowed` hard-coded
  `False`; see `docs/SOURCE_RIGHTS_AND_PROVENANCE.md`). The product must say this explicitly,
  not merely omit a current-season section.
- **Not** a betting or tipping tool. No odds, no "value bet" framing, no stake sizing, no
  gambling-adjacent language anywhere on the page, in its copy, or in any shareable summary.
- **Not** a generic AI-dashboard look — no stock chart-library defaults, no decorative gauges,
  no manufactured confidence theatre. Every number shown must be traceable to a specific,
  reproducible figure in this repository's tracked reports.

## Default model and why

**`team_goal_poisson` is the default.** S05's one specified-protocol Dixon-Coles challenger showed a
small, directionally consistent improvement (log loss 1.0136 vs. 1.0147 overall) but its 95%
descriptive bootstrap interval straddled zero in every scope tested — not strong enough evidence
to adopt the added complexity (`reports/S05_DIXON_COLES_EVALUATION.md`). **The product must not
present `dixon_coles_team_poisson` as the primary forecast.** If a future slice wants to surface
it at all, it should appear labelled explicitly as "an experimental, not-yet-adopted challenger
model," with its own honest caveat, never silently swapped in as if it had earned the default
spot.

## Core screens (described, not built)

1. **Fixture picker.** A simple, filterable list of the 760 evaluated 2024/25 + 2025/26
   fixtures. No fixture outside this exact set is selectable — there is no mechanism to query
   anything from 2023/24 (training-only, never evaluated) or 2026/27 (excluded entirely).
2. **Match view.** For the selected fixture: the actual final score and H/D/A outcome; the
   model's pre-match `[P(H), P(D), P(A)]`; the training-set size (`training_n`) and the latest
   training match date, so a visitor can see exactly how much history informed this specific
   prediction; an explicit "as of" statement (`completed_training_results_as_of`, strictly
   before this fixture's own date); and, where applicable, a cold-start flag with a one-line
   explanation (a promoted/returning team's rate is shrunk toward the league average — see
   `docs/S03_BASELINE_METHODS.md`).
3. **Season scorecard.** For the selected season (2024/25 or 2025/26): the model's aggregate log
   loss, Brier, and RPS (never accuracy alone, never headlined ahead of the proper scores); the
   draw-calibration mean-predicted-vs-observed gap, stated as what it is — a descriptive
   calibration check, not a claim of causal explanation; and a link to the full historical
   finding documents for anyone who wants the underlying methodology.
4. **Methodology note.** A short, plain-English explanation of what the model actually uses
   (team-specific home/away scoring and conceding rates, shrunk with a fixed k=5 pseudo-match
   rule toward the league average), what it explicitly does not use (no injuries, no formations,
   no market odds, no tactical narrative), and the single most important caveat: **both
   evaluated seasons have already been looked at repeatedly during model development, so this
   is a disciplined historical replay, not proof of genuine predictive foresight** — stated in
   the product's own words, not buried in a footnote.

## What the product must never show

- Any 2026/27 fixture, prediction, or implied "current form" statement.
- `dixon_coles_team_poisson`'s output presented without its own adoption caveat, or presented as
  the default.
- Any number not traceable to a tracked report in this repository (no hand-typed statistic, no
  illustrative/placeholder figure left in after launch).
- Any tactical, injury, or narrative claim this results-only corpus cannot support.
- Any accuracy-only headline ahead of the three proper scores.

## Tone and design direction

Restrained, data-led, and explicitly historical — closer to a well-run research lab's public
writeup than a product trying to look impressive. Typography and layout should read as
"football analyst's working notes made presentable," not "generic AI startup landing page."
A single, consistent visual language for probability bars (no gauges, no traffic-light colours
implying a verdict) and for the season scorecard (plain numbers with their N, not a vanity
score). This is the same standard this project has held its written reports to throughout S01–S05;
the product should not relax it just because it is now visual.

## Open questions for whoever builds this next

- Exact page framework/hosting — out of scope for this brief; a decision for the implementation
  slice, informed by whatever first-party tooling is available at that time.
- Whether the methodology note should be a full page or an expandable panel on the match view —
  a UX decision, not a modelling one.
- Whether `dixon_coles_team_poisson` is surfaced at all in the first version, or held back
  entirely until (if ever) a genuinely prospective test changes its adoption status — this brief
  recommends holding it back, but does not mandate it as a hard constraint on a future slice's
  judgement.

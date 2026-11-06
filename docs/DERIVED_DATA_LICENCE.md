# Derived data licence — CC0-1.0 dedication

**Scope:** this notice covers only this project's own *derived, published research
dataset* — `web/public/data/replays.json` (all schema versions) and the machine-readable
audit/report JSON files under `reports/` (e.g. `reports/s04_attribution_metrics.json`,
`reports/s06_public_data_quality.json`). It does not cover this project's own source code
(see the root `LICENSE.md`, MIT), and it is a separate act of dedication from — not an
automatic consequence of — the upstream source data's own CC0 licence (see
`docs/SOURCE_RIGHTS_AND_PROVENANCE.md`).

## Dedication

To the extent possible under law, Aiden Poswell has dedicated all copyright and related or
neighbouring rights that this project's own compilation, selection, and arrangement of the
data listed above might attract, to the public domain worldwide, under the terms of the
**CC0 1.0 Universal** public domain dedication:
<https://creativecommons.org/publicdomain/zero/1.0/>.

You may copy, modify, distribute, and use this derived dataset, even for commercial
purposes, all without asking permission.

## Why CC0, and why this is a separate choice from the code's MIT licence

The underlying fixture and score facts originate from `openfootball/england`
(pinned commit `9ee7a0c351805c99cc334478a9bf04b7d0432fec`), itself CC0-1.0. Releasing this
project's own derived compilation — the per-fixture retrospective probabilities, season
scorecards, and benchmark comparisons computed from that data — under the same CC0 terms
keeps the whole data lineage under one consistent, maximally reusable licence, with no
"research only" or "non-commercial" restriction at any point in the chain.

This is a deliberate choice about *data*, separate from the choice of **MIT** for this
project's own *code* (see the root `LICENSE.md`). A CC0 data release does not make the code
that produces it CC0, and an MIT-licensed codebase does not make its output data MIT —
each is licensed on its own terms.

## What this dedication does not cover

- This project's own source code (Python and TypeScript/React) — see the root `LICENSE.md`.
- Any third party's trademark, such as club or competition names, which this dedication
  neither grants nor restricts.

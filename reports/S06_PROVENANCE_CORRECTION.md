# S06 provenance correction — the S05 "written and committed BEFORE" claim

## What was claimed

Several S05 source comments and docs stated that `docs/S05_DIXON_COLES_PROTOCOL.md` (the
Dixon-Coles challenger protocol) was **"written and committed BEFORE"** the challenger was
fitted or any S05 result was inspected:

- `src/matchweek_intelligence/dixon_coles.py` module docstring
- `reports/S05_DIXON_COLES_EVALUATION.md`
- `docs/S05_DIXON_COLES_PROTOCOL.md`'s own title/intro line

## Why this was not supportable as written

"Written and committed BEFORE" implies an independently verifiable Git record: a commit whose
timestamp (or position in history) proves the protocol document existed, immutably, before the
challenger was fitted — the standard a reader would reasonably associate with the word
"committed" in a version-controlled research repository.

That chronology is **not evidenced**. Per `matchweek-intelligence-s05-verification.md`'s own
Git-state section, S05 — including `docs/S05_DIXON_COLES_PROTOCOL.md`, `dixon_coles.py`, and
every other S05 file — was **left uncommitted throughout its own development**, and was only
committed (as a single unit, alongside everything else) after the S05 slice's work, including
the challenger fit and its evaluation, was already complete. There is no separate, earlier
commit that contains only the frozen protocol and nothing else. Without that, "committed
BEFORE" cannot be independently verified by a reviewer inspecting `git log` — it is, at best, an
internal development-sequence claim being described with a stronger, Git-provenance-implying
word than the actual repository history supports.

To be clear about what is **not** in question: there is no evidence the protocol document was
edited *after* seeing the challenger's result, and the actual chronology within this
development session (protocol text written, then the challenger implemented and run) is not
disputed. What is corrected here is only the *evidentiary strength* of the claim — from "an
independently verifiable pre-registration" to "a specified protocol, documented within the same
development sequence, with no separate immutable checkpoint proving it predated the fit."

## The corrected wording

Each affected location now says, in substance: the protocol was **documented as frozen within
the S05 development sequence**, before the challenger's result was computed or inspected; the
evaluation remained **hindsight-informed** in the broader sense already disclosed elsewhere
(both evaluated seasons had already been looked at repeatedly across S03–S05); and **no
separate pre-fit Git checkpoint is evidenced**. The distinction this project draws is:

- **A specified and followed protocol** (what S05 actually has): constants and rules written
  down in one place, not retroactively edited to match a result, and not chosen from a menu of
  variants after seeing scores — but without an external, time-stamped, tamper-evident record
  proving the writing predated the fitting.
- **An independently pre-registered or blinded study** (what S05 is *not*): a protocol
  deposited somewhere outside the implementer's own control, or committed to immutable history,
  before the implementer could have seen any result — which would make the "before" claim
  independently checkable by a third party without trusting the author's own account of the
  order of events.

## Files corrected in S06

- `src/matchweek_intelligence/dixon_coles.py` — module docstring
- `reports/S05_DIXON_COLES_EVALUATION.md` — title and method-freeze sentence
- `docs/S05_DIXON_COLES_PROTOCOL.md` — title/intro line, plus a correction note; one
  "pre-registered" reference changed to "specified-in-advance" for consistency
- `docs/S05_PUBLIC_PRODUCT_BRIEF.md` — "one pre-registered Dixon-Coles challenger" →
  "one specified-protocol Dixon-Coles challenger"

## What was NOT changed

No experimental numbers, model scores, fitted `rho` values, or prediction rows were altered by
this correction — it is a documentation/wording correction only, verified separately from the
A1–A3 numeric/logic fixes. S05 is still not re-committed as a separate "pre-fit checkpoint";
doing so now and backdating or implying it predated the fit would itself manufacture a false
appearance of pre-registration, which this correction explicitly avoids creating.

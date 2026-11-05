import type { ReplayDataset } from "../types";

export function Methodology({ dataset }: { dataset: ReplayDataset }) {
  return (
    <section aria-labelledby="methodology-heading" className="prose">
      <h2 id="methodology-heading" className="section-label">
        Methodology &amp; limitations
      </h2>

      <h3>What the model actually does</h3>
      <p>
        Every forecast in this replay comes from a single, frozen model:{" "}
        <code>{dataset.model_name}</code>. For a given fixture, it estimates each team's
        attacking and defensive scoring rate independently from that team's own completed
        matches up to (and strictly excluding) the fixture's own date, shrinking a team with a
        short history toward the league-average scoring rate using a fixed pseudo-match rule
        (k = 5 — a promoted or otherwise under-observed team's estimate is pulled proportionally
        further toward the league mean). Those two rates become a pair of expected-goals values,
        which are expanded into a full grid of scoreline probabilities under an independence
        assumption, and finally aggregated into the three outcome probabilities (home win, draw,
        away win) shown on each fixture page. The three probabilities always sum to 100%.
      </p>

      <h3>What it does not use</h3>
      <ul>
        <li>No injuries, suspensions, or starting-lineup information.</li>
        <li>No tactical, managerial, or narrative context of any kind.</li>
        <li>No market odds, no betting lines, and this product makes no betting, staking, or
          value-bet claim anywhere.</li>
        <li>No current or 2026/27 fixture. This dataset contains only completed, scored
          historical matches.</li>
      </ul>

      <h3>A note on timing — read this before trusting any single probability</h3>
      <p>
        {dataset.retrospective_disclosure} Concretely: the pipeline works at the granularity of
        a match <em>date</em>, not a verified kickoff timestamp with timezone, and every match
        played on the same date as the fixture being forecast is excluded from that forecast's
        own training data. This replay never claims a probability was "available at kickoff" —
        only that it used results from strictly before the match date.
      </p>

      <h3>This is a hindsight-informed replay, not a blind test</h3>
      <p>{dataset.hindsight_disclosure} Both evaluated seasons were looked at repeatedly while
        this project's forecasting methods were being built and refined. The per-fixture and
        per-season figures shown here are real and independently reconciled against this
        project's tracked audit reports — but they describe a replay of already-known history,
        not a certified live forecasting record.</p>

      <h3>Why team-goal Poisson, and not something else</h3>
      <p>
        This project also built and evaluated a Dixon-Coles low-score correlation challenger
        against the same 760 fixtures. Its point estimate was marginally better on log loss, but
        the descriptive uncertainty interval around that improvement straddled zero in every
        season and overall — not strong enough evidence to adopt the added complexity.{" "}
        <code>{dataset.model_name}</code> remains the default shown throughout this product; the
        challenger is not surfaced here as a forecast.
      </p>

      <h3>No live or current-season forecasting</h3>
      <p>
        <code>live_claim_allowed</code> is hard-coded to <code>false</code> throughout this
        project. Nothing in this interface, and nothing in the underlying dataset, predicts an
        upcoming or in-progress match. Every number on every page describes a match that had
        already been completed, scored, and recorded in the source data before this replay was
        built.
      </p>

      <h3>Source and rights</h3>
      <p>
        Fixture and score data: <code>{dataset.source.repo}</code>, pinned at commit{" "}
        <code>{dataset.source.pinned_commit}</code>, licensed {dataset.source.license}. This
        derived dataset — fixture identities, actual results, and this one model's pre-match
        probabilities — is published under the same rights-cleared basis as the underlying
        corpus.
      </p>
    </section>
  );
}

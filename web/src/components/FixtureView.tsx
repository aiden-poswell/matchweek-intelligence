import type { Fixture } from "../types";
import { formatMatchDate, seasonLabel } from "../lib/format";
import { ProbabilityBars } from "./ProbabilityBars";

const OUTCOME_LABEL: Record<Fixture["actual_outcome"], (f: Fixture) => string> = {
  H: (f) => `${f.home_team} won`,
  D: () => "Draw",
  A: (f) => `${f.away_team} won`,
};

export function FixtureView({ fixture }: { fixture: Fixture }) {
  const coldStartTeams = [
    fixture.home_team_cold_start ? fixture.home_team : null,
    fixture.away_team_cold_start ? fixture.away_team : null,
  ].filter((x): x is string => x !== null);

  return (
    <article className="fixture-view" aria-labelledby="fixture-view-heading">
      <div className="fixture-view__heading">
        <div>
          <h2 id="fixture-view-heading" className="fixture-view__teams">
            {fixture.home_team} <span aria-hidden="true">v</span>{" "}
            <span className="visually-hidden-label">versus</span> {fixture.away_team}
          </h2>
          <p className="fixture-view__date">
            {formatMatchDate(fixture.match_date)} · {seasonLabel(fixture.season)} Premier League
          </p>
        </div>
        <div className="fixture-view__result">
          <div className="fixture-view__result-label">Actual full-time result</div>
          <div className="fixture-view__score">
            {fixture.home_score}–{fixture.away_score}
          </div>
          <div className="fixture-view__outcome">{OUTCOME_LABEL[fixture.actual_outcome](fixture)}</div>
        </div>
      </div>

      <h3 className="section-label">
        Historical forecast replay (calculated after the match, using only earlier results)
      </h3>
      <ProbabilityBars
        pHome={fixture.p_home}
        pDraw={fixture.p_draw}
        pAway={fixture.p_away}
        homeTeam={fixture.home_team}
        awayTeam={fixture.away_team}
      />

      <h3 className="section-label">What informed this forecast</h3>
      <dl className="training-facts">
        <div className="training-fact">
          <dt>Training sample size</dt>
          <dd>{fixture.training_n} completed Premier League fixtures</dd>
        </div>
        <div className="training-fact">
          <dt>Latest training result used</dt>
          <dd>
            {fixture.latest_training_match_date
              ? formatMatchDate(fixture.latest_training_match_date)
              : "none (first evaluated date)"}
          </dd>
        </div>
        <div className="training-fact">
          <dt>{fixture.home_team} fixtures seen before this match</dt>
          <dd>{fixture.home_team_exposure}</dd>
        </div>
        <div className="training-fact">
          <dt>{fixture.away_team} fixtures seen before this match</dt>
          <dd>{fixture.away_team_exposure}</dd>
        </div>
      </dl>

      <p className="embargo-note">
        This forecast used only results from before {formatMatchDate(fixture.match_date)}. The
        underlying pipeline works at match-date granularity, not a validated kickoff timestamp —
        it was never issued before kickoff, and could not have been issued publicly in advance of
        this match being played.
      </p>

      {coldStartTeams.length > 0 && (
        <p className="cold-start-note">
          Cold-start note: {coldStartTeams.join(" and ")} had no prior fixtures in the training
          window used for this forecast (e.g. recently promoted or at the very start of the
          evaluated history). Its rate was shrunk toward the league-average scoring rate rather
          than estimated from its own results.
        </p>
      )}
    </article>
  );
}

import type { BenchmarkScorecards, Season, SeasonScorecard as SeasonScorecardType } from "../types";
import { seasonLabel } from "../lib/format";

interface Props {
  seasons: Season[];
  season: Season;
  scorecards: Record<Season, SeasonScorecardType>;
  benchmark?: BenchmarkScorecards;
  onSeasonChange: (season: Season) => void;
}

const MODEL_LABEL: Record<string, string> = {
  expanding_league_prior: "Expanding league prior",
  league_only_poisson: "League-only Poisson",
  team_goal_poisson: "Team-goal Poisson",
};

export function SeasonScorecard({ seasons, season, scorecards, benchmark, onSeasonChange }: Props) {
  const card = scorecards[season];

  return (
    <section aria-labelledby="scorecard-heading">
      <h2 id="scorecard-heading" className="section-label">
        Season scorecard
      </h2>
      <div className="season-toggle" role="group" aria-label="Season">
        {seasons.map((s) => (
          <button
            key={s}
            type="button"
            aria-pressed={season === s}
            onClick={() => onSeasonChange(s)}
          >
            {seasonLabel(s)}
          </button>
        ))}
      </div>

      <p className="fixture-count-note" style={{ marginTop: "0.75rem" }}>
        N = {card.n} evaluated fixtures. Every figure below is computed from this project's
        frozen <code>team_goal_poisson</code> model and reconciled against the project's tracked
        audit reports — never hand-entered.
      </p>

      <div className="scorecard-grid">
        <div className="stat-card">
          <p className="stat-card__label">Log loss</p>
          <p className="stat-card__value">{card.log_loss.toFixed(4)}</p>
          <p className="stat-card__hint">Lower is better · proper scoring rule</p>
        </div>
        <div className="stat-card">
          <p className="stat-card__label">Brier score</p>
          <p className="stat-card__value">{card.brier.toFixed(4)}</p>
          <p className="stat-card__hint">Lower is better · range 0–2</p>
        </div>
        <div className="stat-card">
          <p className="stat-card__label">RPS</p>
          <p className="stat-card__value">{card.rps.toFixed(4)}</p>
          <p className="stat-card__hint">Lower is better · ranked probability score</p>
        </div>
      </div>

      <h3 className="section-label" style={{ marginTop: "1.5rem" }}>
        Draw calibration
      </h3>
      <table className="draw-calibration-table">
        <thead>
          <tr>
            <th scope="col">Quantity</th>
            <th scope="col">Value</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td>Mean predicted draw probability</td>
            <td className="num">{card.draw_calibration.mean_predicted_pct.toFixed(2)}%</td>
          </tr>
          <tr>
            <td>Observed draw rate</td>
            <td className="num">{card.draw_calibration.observed_pct.toFixed(2)}%</td>
          </tr>
          <tr>
            <td>Gap (observed − predicted)</td>
            <td className="num">
              {card.draw_calibration.gap_pct_points_observed_minus_predicted >= 0 ? "+" : ""}
              {card.draw_calibration.gap_pct_points_observed_minus_predicted.toFixed(2)} pp
            </td>
          </tr>
        </tbody>
      </table>
      <p className="fixture-count-note" style={{ marginTop: "0.5rem" }}>
        A positive gap means draws happened slightly more often than this model predicted on
        average, across the season — a descriptive calibration check, not a causal explanation.
        See Methodology for the full discussion, including the evaluated-but-not-adopted
        Dixon-Coles challenger.
      </p>

      {benchmark && (
        <>
          <h3 className="section-label" style={{ marginTop: "1.5rem" }}>
            Why team-goal Poisson
          </h3>
          <table className="draw-calibration-table" aria-describedby="benchmark-disclosure">
            <thead>
              <tr>
                <th scope="col">Baseline</th>
                <th scope="col">Log loss</th>
                <th scope="col">Brier</th>
                <th scope="col">RPS</th>
              </tr>
            </thead>
            <tbody>
              {benchmark.models.map((model) => {
                const m = benchmark.by_season[season][model];
                const isAdopted = model === "team_goal_poisson";
                return (
                  <tr key={model} aria-current={isAdopted ? "true" : undefined}>
                    <td>
                      {MODEL_LABEL[model] ?? model}
                      {isAdopted ? " (adopted default)" : ""}
                    </td>
                    <td className="num">{m.log_loss.toFixed(4)}</td>
                    <td className="num">{m.brier.toFixed(4)}</td>
                    <td className="num">{m.rps.toFixed(4)}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
          <p className="fixture-count-note" id="benchmark-disclosure" style={{ marginTop: "0.5rem" }}>
            {seasonLabel(season)} only, N = {benchmark.by_season[season].team_goal_poisson.n}.
            Overall across both evaluated seasons (N = {benchmark.overall.team_goal_poisson.n}),
            team-goal Poisson log loss is {benchmark.overall.team_goal_poisson.log_loss.toFixed(4)}
            {" "}vs. {benchmark.overall.league_only_poisson.log_loss.toFixed(4)} (league-only
            Poisson) and {benchmark.overall.expanding_league_prior.log_loss.toFixed(4)} (expanding
            league prior). {benchmark.disclosure}
          </p>
        </>
      )}
    </section>
  );
}

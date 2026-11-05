import type { Fixture, ReplayDataset } from "../types";

export function makeFixture(overrides: Partial<Fixture> = {}): Fixture {
  return {
    id: "2024-08-16--alpha-fc--vs--beta-fc",
    season: "2024-25",
    match_date: "2024-08-16",
    home_team: "Alpha FC",
    away_team: "Beta FC",
    home_score: 2,
    away_score: 1,
    actual_outcome: "H",
    p_home: 0.5,
    p_draw: 0.3,
    p_away: 0.2,
    training_n: 10,
    latest_training_match_date: "2024-05-19",
    home_team_exposure: 5,
    away_team_exposure: 5,
    home_team_cold_start: false,
    away_team_cold_start: false,
    ...overrides,
  };
}

export function makeDataset(overrides: Partial<ReplayDataset> = {}): ReplayDataset {
  const fixtures = overrides.fixtures ?? [
    makeFixture(),
    makeFixture({
      id: "2024-09-01--gamma-fc--vs--delta-fc",
      match_date: "2024-09-01",
      home_team: "Gamma FC",
      away_team: "Delta FC",
      actual_outcome: "D",
      home_score: 1,
      away_score: 1,
    }),
    makeFixture({
      id: "2025-08-16--alpha-fc--vs--gamma-fc",
      season: "2025-26",
      match_date: "2025-08-16",
      home_team: "Alpha FC",
      away_team: "Gamma FC",
    }),
  ];
  return {
    schema_version: "1.0.0",
    model_name: "team_goal_poisson",
    retrospective: true,
    live_claim_allowed: false,
    source: {
      repo: "openfootball/england",
      pinned_commit: "9ee7a0c351805c99cc334478a9bf04b7d0432fec",
      license: "CC0-1.0",
    },
    retrospective_disclosure: "Every probability shown here was computed retrospectively.",
    hindsight_disclosure: "Both evaluated seasons have already been inspected repeatedly.",
    training_only_seasons: ["2023-24"],
    evaluation_seasons: ["2024-25", "2025-26"],
    outcome_order: ["H", "D", "A"],
    fixture_count: fixtures.length,
    fixtures,
    season_scorecards: {
      "2024-25": {
        n: 2,
        log_loss: 0.99,
        brier: 0.6,
        rps: 0.2,
        draw_calibration: {
          mean_predicted_pct: 22.0,
          observed_pct: 25.0,
          gap_pct_points_observed_minus_predicted: 3.0,
        },
      },
      "2025-26": {
        n: 1,
        log_loss: 1.02,
        brier: 0.62,
        rps: 0.21,
        draw_calibration: {
          mean_predicted_pct: 23.0,
          observed_pct: 20.0,
          gap_pct_points_observed_minus_predicted: -3.0,
        },
      },
    },
    ...overrides,
  };
}

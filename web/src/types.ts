export type Season = "2024-25" | "2025-26";
export type Outcome = "H" | "D" | "A";

export interface Fixture {
  id: string;
  season: Season;
  match_date: string;
  home_team: string;
  away_team: string;
  home_score: number;
  away_score: number;
  actual_outcome: Outcome;
  p_home: number;
  p_draw: number;
  p_away: number;
  training_n: number;
  latest_training_match_date: string;
  home_team_exposure: number;
  away_team_exposure: number;
  home_team_cold_start: boolean;
  away_team_cold_start: boolean;
}

export interface DrawCalibration {
  mean_predicted_pct: number;
  observed_pct: number;
  gap_pct_points_observed_minus_predicted: number;
}

export interface SeasonScorecard {
  n: number;
  log_loss: number;
  brier: number;
  rps: number;
  draw_calibration: DrawCalibration;
}

export interface BenchmarkModelMetrics {
  n: number;
  log_loss: number;
  brier: number;
  rps: number;
}

export interface BenchmarkScorecards {
  models: string[];
  lower_is_better: boolean;
  disclosure: string;
  by_season: Record<Season, Record<string, BenchmarkModelMetrics>>;
  overall: Record<string, BenchmarkModelMetrics>;
}

export interface ReplayDataset {
  schema_version: string;
  model_name: string;
  retrospective: boolean;
  live_claim_allowed: boolean;
  source: {
    repo: string;
    pinned_commit: string;
    license: string;
  };
  retrospective_disclosure: string;
  hindsight_disclosure: string;
  training_only_seasons: string[];
  evaluation_seasons: Season[];
  outcome_order: Outcome[];
  fixture_count: number;
  fixtures: Fixture[];
  season_scorecards: Record<Season, SeasonScorecard>;
  benchmark_scorecards?: BenchmarkScorecards;
}

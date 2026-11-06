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

// --- A full, strictly-valid 760-fixture dataset -------------------------------------
//
// App.test.tsx renders the real <App/>, which runs every fetched dataset through the
// actual browser-side `validateReplayDataset` trust boundary (Stage B) — so it needs
// a dataset that genuinely satisfies that contract (exactly 760 fixtures, 380 per
// season, scorecards that independently reconcile), not the small illustrative
// dataset `makeDataset()` returns for component-level prop tests. The three named
// fixtures App.test.tsx's assertions depend on (Alpha FC v Beta FC, Gamma FC v Delta
// FC, Alpha FC v Gamma FC) are included verbatim; the remaining fixtures are
// synthetic filler with deliberately distinct team names so they can never be
// confused with the named ones by the club-search tests.

function logLossLocal(p: number): number {
  return -Math.log(p);
}

function brierLocal(pHome: number, pDraw: number, pAway: number, outcome: "H" | "D" | "A"): number {
  const probs = { H: pHome, D: pDraw, A: pAway };
  return (["H", "D", "A"] as const).reduce(
    (sum, o) => sum + (probs[o] - (o === outcome ? 1 : 0)) ** 2,
    0,
  );
}

function rpsLocal(pHome: number, pDraw: number, _pAway: number, outcome: "H" | "D" | "A"): number {
  const c1 = pHome;
  const c2 = pHome + pDraw;
  const o1 = outcome === "H" ? 1 : 0;
  const o2 = outcome === "H" || outcome === "D" ? 1 : 0;
  return ((c1 - o1) ** 2 + (c2 - o2) ** 2) / 2;
}

function makeFillerFixture(season: "2024-25" | "2025-26", index: number): Fixture {
  // Starts strictly AFTER the latest named fixture date in each season (2024-09-01
  // for 2024-25; 2025-08-16 for 2025-26), so no filler fixture can ever become the
  // dataset's chronologically earliest fixture and silently change which fixture
  // App.test.tsx's "default selection" assertions expect.
  const base = season === "2024-25" ? Date.UTC(2024, 8, 2) : Date.UTC(2025, 7, 17);
  const match_date = new Date(base + index * 86_400_000).toISOString().slice(0, 10);
  const prevDate = new Date(base + (index - 1) * 86_400_000).toISOString().slice(0, 10);
  const outcomes: ("H" | "D" | "A")[] = ["H", "D", "A"];
  const outcome = outcomes[index % 3];
  const [home_score, away_score] =
    outcome === "H" ? [2, 0] : outcome === "D" ? [1, 1] : [0, 2];
  return {
    id: `${match_date}--filler-home-${season}-${index}--vs--filler-away-${season}-${index}`,
    season,
    match_date,
    home_team: `Filler Home ${season} ${index}`,
    away_team: `Filler Away ${season} ${index}`,
    home_score,
    away_score,
    actual_outcome: outcome,
    p_home: 0.4,
    p_draw: 0.3,
    p_away: 0.3,
    training_n: index,
    latest_training_match_date: index === 0 ? "" : prevDate,
    home_team_exposure: 0,
    away_team_exposure: 0,
    home_team_cold_start: false,
    away_team_cold_start: false,
  };
}

function recomputeScorecard(seasonFixtures: Fixture[]) {
  const n = seasonFixtures.length;
  let totalLogLoss = 0;
  let totalBrier = 0;
  let totalRps = 0;
  let drawCount = 0;
  let sumPredictedDraw = 0;
  for (const f of seasonFixtures) {
    const pObserved =
      f.actual_outcome === "H" ? f.p_home : f.actual_outcome === "D" ? f.p_draw : f.p_away;
    totalLogLoss += logLossLocal(pObserved);
    totalBrier += brierLocal(f.p_home, f.p_draw, f.p_away, f.actual_outcome);
    totalRps += rpsLocal(f.p_home, f.p_draw, f.p_away, f.actual_outcome);
    sumPredictedDraw += f.p_draw;
    if (f.actual_outcome === "D") drawCount += 1;
  }
  const meanPredictedPct = (sumPredictedDraw / n) * 100;
  const observedPct = (drawCount / n) * 100;
  return {
    n,
    log_loss: totalLogLoss / n,
    brier: totalBrier / n,
    rps: totalRps / n,
    draw_calibration: {
      mean_predicted_pct: meanPredictedPct,
      observed_pct: observedPct,
      gap_pct_points_observed_minus_predicted: observedPct - meanPredictedPct,
    },
  };
}

export function makeFullValidDataset(): ReplayDataset {
  const named2425 = [
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
  ];
  const named2526 = [
    makeFixture({
      id: "2025-08-16--alpha-fc--vs--gamma-fc",
      season: "2025-26",
      match_date: "2025-08-16",
      home_team: "Alpha FC",
      away_team: "Gamma FC",
    }),
  ];

  const filler2425 = Array.from({ length: 380 - named2425.length }, (_, i) =>
    makeFillerFixture("2024-25", i),
  );
  const filler2526 = Array.from({ length: 380 - named2526.length }, (_, i) =>
    makeFillerFixture("2025-26", i),
  );

  const fixtures2425 = [...named2425, ...filler2425];
  const fixtures2526 = [...named2526, ...filler2526];
  const fixtures = [...fixtures2425, ...fixtures2526];

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
      "2024-25": recomputeScorecard(fixtures2425),
      "2025-26": recomputeScorecard(fixtures2526),
    },
  };
}

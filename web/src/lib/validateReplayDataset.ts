import type { Fixture, ReplayDataset, Season, SeasonScorecard } from "../types";

export type ValidationResult =
  | { ok: true; data: ReplayDataset }
  | { ok: false; error: string };

const EXPECTED_SCHEMA_VERSION = "1.0.0";
const EXPECTED_MODEL_NAME = "team_goal_poisson";
const EXPECTED_SOURCE_REPO = "openfootball/england";
const EXPECTED_PINNED_COMMIT = "9ee7a0c351805c99cc334478a9bf04b7d0432fec";
const EXPECTED_LICENSE = "CC0-1.0";
const SUPPORTED_SEASONS: readonly Season[] = ["2024-25", "2025-26"];
const EXPECTED_N_PER_SEASON = 380;
const EXPECTED_TOTAL = 760;
const PROBABILITY_TOLERANCE = 1e-6;
const METRIC_RECONCILE_TOLERANCE = 1e-4;

const ISO_DATE_RE = /^\d{4}-\d{2}-\d{2}$/;

function fail(error: string): ValidationResult {
  return { ok: false, error };
}

function isPlainObject(x: unknown): x is Record<string, unknown> {
  return typeof x === "object" && x !== null && !Array.isArray(x);
}

function isValidIsoDate(s: unknown): s is string {
  if (typeof s !== "string" || !ISO_DATE_RE.test(s)) return false;
  const d = new Date(`${s}T00:00:00Z`);
  return !Number.isNaN(d.getTime()) && d.toISOString().slice(0, 10) === s;
}

function deriveOutcome(homeScore: number, awayScore: number): "H" | "D" | "A" {
  if (homeScore > awayScore) return "H";
  if (homeScore === awayScore) return "D";
  return "A";
}

// --- Independent scoring-rule recomputation (mirrors metrics.py's conventions:
// OUTCOME_ORDER = H, D, A; three-component Brier; RPS cumulated at the H|D boundary,
// divided by 2) — never trusts the published scorecard numbers without rederiving
// them from the raw per-fixture probabilities and actual outcomes. -----------------

function logLoss(pObserved: number): number {
  return -Math.log(pObserved);
}

function brierScore(pHome: number, pDraw: number, pAway: number, outcome: "H" | "D" | "A"): number {
  const probs = { H: pHome, D: pDraw, A: pAway };
  return (["H", "D", "A"] as const).reduce(
    (sum, o) => sum + (probs[o] - (o === outcome ? 1 : 0)) ** 2,
    0,
  );
}

function rankedProbabilityScore(
  pHome: number,
  pDraw: number,
  _pAway: number,
  outcome: "H" | "D" | "A",
): number {
  const c1 = pHome;
  const c2 = pHome + pDraw;
  const o1 = outcome === "H" ? 1 : 0;
  const o2 = outcome === "H" || outcome === "D" ? 1 : 0;
  return ((c1 - o1) ** 2 + (c2 - o2) ** 2) / 2;
}

function validateFixtureShape(raw: unknown, index: number): raw is Fixture {
  if (!isPlainObject(raw)) return false;
  const f = raw;
  if (typeof f.id !== "string" || f.id === "") return false;
  if (!isValidIsoDate(f.match_date)) return false;
  if (typeof f.home_team !== "string" || f.home_team === "") return false;
  if (typeof f.away_team !== "string" || f.away_team === "") return false;
  if (
    typeof f.home_score !== "number" ||
    !Number.isInteger(f.home_score) ||
    f.home_score < 0 ||
    typeof f.away_score !== "number" ||
    !Number.isInteger(f.away_score) ||
    f.away_score < 0
  ) {
    return false;
  }
  if (f.actual_outcome !== "H" && f.actual_outcome !== "D" && f.actual_outcome !== "A") {
    return false;
  }
  if (deriveOutcome(f.home_score as number, f.away_score as number) !== f.actual_outcome) {
    return false;
  }
  for (const key of ["p_home", "p_draw", "p_away"] as const) {
    const p = f[key];
    if (typeof p !== "number" || !Number.isFinite(p) || p <= 0 || p >= 1) return false;
  }
  const total = (f.p_home as number) + (f.p_draw as number) + (f.p_away as number);
  if (Math.abs(total - 1) > PROBABILITY_TOLERANCE) return false;
  if (typeof f.training_n !== "number" || !Number.isInteger(f.training_n) || f.training_n < 0) {
    return false;
  }
  if (typeof f.latest_training_match_date !== "string") return false;
  if (f.latest_training_match_date !== "" && !isValidIsoDate(f.latest_training_match_date)) {
    return false;
  }
  if (
    f.latest_training_match_date !== "" &&
    (f.latest_training_match_date as string) >= (f.match_date as string)
  ) {
    // A same-day-or-later "latest training result" would mean this fixture's own
    // (or a same-day/future) result leaked into its own training data.
    return false;
  }
  if (typeof f.home_team_exposure !== "number" || f.home_team_exposure < 0) return false;
  if (typeof f.away_team_exposure !== "number" || f.away_team_exposure < 0) return false;
  if (typeof f.home_team_cold_start !== "boolean") return false;
  if (typeof f.away_team_cold_start !== "boolean") return false;
  if (f.season !== "2024-25" && f.season !== "2025-26") return false;
  void index;
  return true;
}

function validateScorecardShape(raw: unknown): raw is SeasonScorecard {
  if (!isPlainObject(raw)) return false;
  const s = raw;
  if (typeof s.n !== "number" || !Number.isFinite(s.n) || s.n <= 0) return false;
  if (typeof s.log_loss !== "number" || !Number.isFinite(s.log_loss)) return false;
  if (typeof s.brier !== "number" || !Number.isFinite(s.brier)) return false;
  if (typeof s.rps !== "number" || !Number.isFinite(s.rps)) return false;
  if (!isPlainObject(s.draw_calibration)) return false;
  const dc = s.draw_calibration;
  for (const key of ["mean_predicted_pct", "observed_pct", "gap_pct_points_observed_minus_predicted"]) {
    if (typeof dc[key] !== "number" || !Number.isFinite(dc[key] as number)) return false;
  }
  return true;
}

/**
 * The browser's own trust boundary: a strict, fail-closed runtime contract check
 * run on every fetched dataset before it is ever rendered. This is independent of
 * — and does not assume anything about — the Python generator's own checks; a
 * tampered, truncated, or malformed `replays.json` is rejected here even if it was
 * never caught upstream. Never mutates or "fixes up" a bad row into a valid-looking
 * one: the first violation found causes the whole dataset to be rejected.
 */
export function validateReplayDataset(raw: unknown): ValidationResult {
  if (!isPlainObject(raw)) {
    return fail("replay data is not a JSON object");
  }

  if (raw.schema_version !== EXPECTED_SCHEMA_VERSION) {
    return fail(`unexpected schema_version: ${JSON.stringify(raw.schema_version)}`);
  }
  if (raw.model_name !== EXPECTED_MODEL_NAME) {
    return fail(`unexpected model_name: ${JSON.stringify(raw.model_name)}`);
  }
  if (raw.retrospective !== true) {
    return fail("retrospective must be true");
  }
  if (raw.live_claim_allowed !== false) {
    return fail("live_claim_allowed must be false — refusing a dataset that claims a live feed");
  }
  if (!isPlainObject(raw.source)) {
    return fail("missing source provenance block");
  }
  const source = raw.source;
  if (source.repo !== EXPECTED_SOURCE_REPO) {
    return fail(`unexpected source.repo: ${JSON.stringify(source.repo)}`);
  }
  if (source.pinned_commit !== EXPECTED_PINNED_COMMIT) {
    return fail(`unexpected source.pinned_commit: ${JSON.stringify(source.pinned_commit)}`);
  }
  if (source.license !== EXPECTED_LICENSE) {
    return fail(`unexpected source.license: ${JSON.stringify(source.license)}`);
  }
  if (
    !Array.isArray(raw.evaluation_seasons) ||
    raw.evaluation_seasons.length !== SUPPORTED_SEASONS.length ||
    !SUPPORTED_SEASONS.every((s) => (raw.evaluation_seasons as unknown[]).includes(s))
  ) {
    return fail(`unexpected evaluation_seasons: ${JSON.stringify(raw.evaluation_seasons)}`);
  }

  if (!Array.isArray(raw.fixtures)) {
    return fail("fixtures is not an array");
  }
  if (raw.fixtures.length !== EXPECTED_TOTAL) {
    return fail(`expected ${EXPECTED_TOTAL} fixtures, found ${raw.fixtures.length}`);
  }
  if (typeof raw.fixture_count !== "number" || raw.fixture_count !== raw.fixtures.length) {
    return fail("fixture_count does not match the fixture list length");
  }

  const seenIds = new Set<string>();
  const seenKeys = new Set<string>();
  const perSeasonCount: Record<string, number> = { "2024-25": 0, "2025-26": 0 };

  for (let i = 0; i < raw.fixtures.length; i++) {
    const f = raw.fixtures[i];
    if (!validateFixtureShape(f, i)) {
      return fail(`fixture at index ${i} failed validation: ${JSON.stringify(f)}`);
    }
    const fixture = f as Fixture;
    if (fixture.season !== "2024-25" && fixture.season !== "2025-26") {
      return fail(`fixture at index ${i} has an unsupported season: ${fixture.season}`);
    }
    if ((fixture.season as string) === "2026-27") {
      return fail("a 2026/27 fixture is present — refusing a dataset implying a current feed");
    }
    if (seenIds.has(fixture.id)) {
      return fail(`duplicate fixture id: ${fixture.id}`);
    }
    seenIds.add(fixture.id);
    const key = `${fixture.match_date}__${fixture.home_team}__${fixture.away_team}`;
    if (seenKeys.has(key)) {
      return fail(`duplicate fixture key: ${key}`);
    }
    seenKeys.add(key);
    perSeasonCount[fixture.season] += 1;
  }

  for (const season of SUPPORTED_SEASONS) {
    if (perSeasonCount[season] !== EXPECTED_N_PER_SEASON) {
      return fail(
        `season ${season}: expected ${EXPECTED_N_PER_SEASON} fixtures, found ${perSeasonCount[season]}`,
      );
    }
  }

  if (!isPlainObject(raw.season_scorecards)) {
    return fail("missing season_scorecards");
  }
  const scorecards = raw.season_scorecards;
  for (const season of SUPPORTED_SEASONS) {
    if (!validateScorecardShape(scorecards[season])) {
      return fail(`season_scorecards.${season} is missing or malformed`);
    }
  }

  // Independently recompute every season's log loss, Brier, RPS, and draw
  // calibration directly from the 760 fixtures — never trust the published
  // scorecard numbers without rederiving them. A material disagreement here means
  // the scorecard and the fixture rows were generated from different data (or one
  // was tampered with), and the whole dataset is rejected rather than displayed.
  const fixtures = raw.fixtures as Fixture[];
  for (const season of SUPPORTED_SEASONS) {
    const seasonFixtures = fixtures.filter((f) => f.season === season);
    const n = seasonFixtures.length;
    let totalLogLoss = 0;
    let totalBrier = 0;
    let totalRps = 0;
    let drawCount = 0;
    let sumPredictedDraw = 0;
    for (const f of seasonFixtures) {
      const pObserved =
        f.actual_outcome === "H" ? f.p_home : f.actual_outcome === "D" ? f.p_draw : f.p_away;
      totalLogLoss += logLoss(pObserved);
      totalBrier += brierScore(f.p_home, f.p_draw, f.p_away, f.actual_outcome);
      totalRps += rankedProbabilityScore(f.p_home, f.p_draw, f.p_away, f.actual_outcome);
      sumPredictedDraw += f.p_draw;
      if (f.actual_outcome === "D") drawCount += 1;
    }
    const recomputed = {
      log_loss: totalLogLoss / n,
      brier: totalBrier / n,
      rps: totalRps / n,
      mean_predicted_pct: (sumPredictedDraw / n) * 100,
      observed_pct: (drawCount / n) * 100,
    };
    const published = scorecards[season] as SeasonScorecard;
    if (published.n !== n) {
      return fail(
        `season_scorecards.${season}.n (${published.n}) disagrees with the fixture count (${n})`,
      );
    }
    const checks: [string, number, number][] = [
      ["log_loss", recomputed.log_loss, published.log_loss],
      ["brier", recomputed.brier, published.brier],
      ["rps", recomputed.rps, published.rps],
      [
        "draw_calibration.mean_predicted_pct",
        recomputed.mean_predicted_pct,
        published.draw_calibration.mean_predicted_pct,
      ],
      [
        "draw_calibration.observed_pct",
        recomputed.observed_pct,
        published.draw_calibration.observed_pct,
      ],
    ];
    for (const [label, recomputedValue, publishedValue] of checks) {
      if (Math.abs(recomputedValue - publishedValue) > METRIC_RECONCILE_TOLERANCE) {
        return fail(
          `season ${season} ${label}: recomputed ${recomputedValue} disagrees with published ` +
            `${publishedValue} (tolerance ${METRIC_RECONCILE_TOLERANCE})`,
        );
      }
    }
  }

  return { ok: true, data: raw as unknown as ReplayDataset };
}

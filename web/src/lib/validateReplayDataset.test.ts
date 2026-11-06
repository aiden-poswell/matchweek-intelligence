import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";
import { validateReplayDataset } from "./validateReplayDataset";
import { makeFullValidDataset } from "../test/fixtures";
import type { ReplayDataset } from "../types";

function clone(dataset: ReplayDataset): ReplayDataset {
  return JSON.parse(JSON.stringify(dataset));
}

describe("validateReplayDataset", () => {
  it("accepts a genuinely valid, full-shape 760-fixture dataset", () => {
    const dataset = makeFullValidDataset();
    const result = validateReplayDataset(dataset);
    expect(result.ok).toBe(true);
  });

  it("rejects malformed JSON (not even an object)", () => {
    expect(validateReplayDataset("just a string").ok).toBe(false);
    expect(validateReplayDataset(null).ok).toBe(false);
    expect(validateReplayDataset([1, 2, 3]).ok).toBe(false);
    expect(validateReplayDataset(42).ok).toBe(false);
  });

  it("rejects an unexpected model name", () => {
    const dataset = clone(makeFullValidDataset());
    (dataset as unknown as Record<string, unknown>).model_name = "dixon_coles_team_poisson";
    const result = validateReplayDataset(dataset);
    expect(result.ok).toBe(false);
    if (!result.ok) expect(result.error).toMatch(/model_name/);
  });

  it("rejects live_claim_allowed: true — refuses anything implying a live feed", () => {
    const dataset = clone(makeFullValidDataset());
    (dataset as unknown as Record<string, unknown>).live_claim_allowed = true;
    const result = validateReplayDataset(dataset);
    expect(result.ok).toBe(false);
    if (!result.ok) expect(result.error).toMatch(/live_claim_allowed/);
  });

  it("rejects a 2026/27 fixture", () => {
    const dataset = clone(makeFullValidDataset());
    (dataset.fixtures[0] as unknown as Record<string, unknown>).season = "2026-27";
    const result = validateReplayDataset(dataset);
    expect(result.ok).toBe(false);
    if (!result.ok) expect(result.error).toMatch(/2026-27|unsupported season/);
  });

  it("rejects a duplicate fixture id", () => {
    const dataset = clone(makeFullValidDataset());
    dataset.fixtures[1].id = dataset.fixtures[0].id;
    const result = validateReplayDataset(dataset);
    expect(result.ok).toBe(false);
    if (!result.ok) expect(result.error).toMatch(/duplicate fixture id/);
  });

  it("rejects a duplicate fixture key even with distinct ids", () => {
    const dataset = clone(makeFullValidDataset());
    dataset.fixtures[1].id = "a-totally-different-id";
    dataset.fixtures[1].match_date = dataset.fixtures[0].match_date;
    dataset.fixtures[1].home_team = dataset.fixtures[0].home_team;
    dataset.fixtures[1].away_team = dataset.fixtures[0].away_team;
    const result = validateReplayDataset(dataset);
    expect(result.ok).toBe(false);
    if (!result.ok) expect(result.error).toMatch(/duplicate fixture key/);
  });

  it("rejects a fixture whose actual_outcome contradicts its own score", () => {
    const dataset = clone(makeFullValidDataset());
    dataset.fixtures[0].home_score = 5;
    dataset.fixtures[0].away_score = 0;
    dataset.fixtures[0].actual_outcome = "A"; // contradicts a 5-0 home win
    const result = validateReplayDataset(dataset);
    expect(result.ok).toBe(false);
    if (!result.ok) expect(result.error).toMatch(/failed validation/);
  });

  it("rejects a probability that is zero, one, or out of [0,1]", () => {
    for (const bad of [0, 1, -0.1, 1.1, Number.NaN, Number.POSITIVE_INFINITY]) {
      const dataset = clone(makeFullValidDataset());
      dataset.fixtures[0].p_home = bad;
      dataset.fixtures[0].p_draw = 0.3;
      dataset.fixtures[0].p_away = 1 - bad - 0.3;
      const result = validateReplayDataset(dataset);
      expect(result.ok).toBe(false);
    }
  });

  it("rejects probabilities that do not sum to 1", () => {
    const dataset = clone(makeFullValidDataset());
    dataset.fixtures[0].p_home = 0.5;
    dataset.fixtures[0].p_draw = 0.5;
    dataset.fixtures[0].p_away = 0.5; // sums to 1.5
    const result = validateReplayDataset(dataset);
    expect(result.ok).toBe(false);
  });

  it("rejects a training cutoff on or after the fixture's own match date", () => {
    const dataset = clone(makeFullValidDataset());
    dataset.fixtures[0].latest_training_match_date = dataset.fixtures[0].match_date;
    const result = validateReplayDataset(dataset);
    expect(result.ok).toBe(false);
  });

  it("rejects a missing season scorecard", () => {
    const dataset = clone(makeFullValidDataset()) as unknown as Record<string, unknown>;
    const scorecards = dataset.season_scorecards as Record<string, unknown>;
    delete scorecards["2025-26"];
    const result = validateReplayDataset(dataset);
    expect(result.ok).toBe(false);
    if (!result.ok) expect(result.error).toMatch(/season_scorecards/);
  });

  it("rejects a season scorecard whose published metric disagrees with the recomputed one", () => {
    const dataset = clone(makeFullValidDataset());
    dataset.season_scorecards["2024-25"].log_loss = 999; // deliberately wrong
    const result = validateReplayDataset(dataset);
    expect(result.ok).toBe(false);
    if (!result.ok) expect(result.error).toMatch(/log_loss/);
  });

  it("rejects a season scorecard whose published draw calibration disagrees with the recomputed one", () => {
    const dataset = clone(makeFullValidDataset());
    dataset.season_scorecards["2024-25"].draw_calibration.observed_pct = 0;
    const result = validateReplayDataset(dataset);
    expect(result.ok).toBe(false);
    if (!result.ok) expect(result.error).toMatch(/observed_pct/);
  });

  it("rejects a season scorecard whose N disagrees with the actual fixture count for that season", () => {
    const dataset = clone(makeFullValidDataset());
    dataset.season_scorecards["2024-25"].n = 1;
    const result = validateReplayDataset(dataset);
    expect(result.ok).toBe(false);
    if (!result.ok) expect(result.error).toMatch(/disagrees with the fixture count/);
  });

  it("rejects a dataset with the wrong total fixture count", () => {
    const dataset = clone(makeFullValidDataset());
    dataset.fixtures.pop();
    dataset.fixture_count = dataset.fixtures.length;
    const result = validateReplayDataset(dataset);
    expect(result.ok).toBe(false);
    if (!result.ok) expect(result.error).toMatch(/expected 760 fixtures|expected 380 fixtures/);
  });

  it("rejects an unsupported source repo or pinned commit (tampered provenance)", () => {
    const d1 = clone(makeFullValidDataset());
    d1.source.repo = "someone-else/fork";
    expect(validateReplayDataset(d1).ok).toBe(false);

    const d2 = clone(makeFullValidDataset());
    d2.source.pinned_commit = "0".repeat(40);
    expect(validateReplayDataset(d2).ok).toBe(false);
  });

  it("accepts the REAL, generated web/public/data/replays.json unchanged (acceptance test)", () => {
    const here = dirname(fileURLToPath(import.meta.url));
    const realPath = resolve(here, "../../public/data/replays.json");
    const raw = JSON.parse(readFileSync(realPath, "utf-8"));
    const result = validateReplayDataset(raw);
    if (!result.ok) {
      throw new Error(`real replays.json failed browser-side validation: ${result.error}`);
    }
    expect(result.data.fixture_count).toBe(760);
    expect(result.data.fixtures).toHaveLength(760);
  });

  describe("S08: closes the three reviewer-identified fail-open adversarial mutations", () => {
    function loadRealDataset(): ReplayDataset {
      const here = dirname(fileURLToPath(import.meta.url));
      const realPath = resolve(here, "../../public/data/replays.json");
      return JSON.parse(readFileSync(realPath, "utf-8")) as ReplayDataset;
    }

    it("accepts the untouched real dataset (control)", () => {
      const result = validateReplayDataset(loadRealDataset());
      expect(result.ok).toBe(true);
    });

    it("rejects a fabricated +999pp draw-calibration gap", () => {
      const changedGap = loadRealDataset();
      changedGap.season_scorecards["2024-25"].draw_calibration.gap_pct_points_observed_minus_predicted = 999;
      const result = validateReplayDataset(changedGap);
      expect(result.ok).toBe(false);
      if (!result.ok) expect(result.error).toMatch(/gap_pct_points_observed_minus_predicted/);
    });

    it("rejects a cold_start flag flipped true alongside a nonzero exposure", () => {
      const changedCold = loadRealDataset();
      const fixture = changedCold.fixtures[0];
      // Guard the premise: this only exercises the bug if the real fixture's own
      // exposure is genuinely nonzero (i.e. cold_start is correctly false already).
      expect(fixture.home_team_exposure).toBeGreaterThan(0);
      expect(fixture.home_team_cold_start).toBe(false);
      fixture.home_team_cold_start = true;
      const result = validateReplayDataset(changedCold);
      expect(result.ok).toBe(false);
      if (!result.ok) expect(result.error).toMatch(/failed validation/);
    });

    it("rejects a fractional exposure count", () => {
      const fractional = loadRealDataset();
      fractional.fixtures[0].home_team_exposure = 3.25;
      const result = validateReplayDataset(fractional);
      expect(result.ok).toBe(false);
      if (!result.ok) expect(result.error).toMatch(/failed validation/);
    });
  });

  describe("S08: benchmark_scorecards validation", () => {
    it("rejects a dataset missing benchmark_scorecards entirely", () => {
      const dataset = clone(makeFullValidDataset()) as unknown as Record<string, unknown>;
      delete dataset.benchmark_scorecards;
      const result = validateReplayDataset(dataset);
      expect(result.ok).toBe(false);
      if (!result.ok) expect(result.error).toMatch(/missing benchmark_scorecards/);
    });

    it("rejects an unexpected benchmark model list or order", () => {
      const dataset = clone(makeFullValidDataset());
      dataset.benchmark_scorecards!.models = ["team_goal_poisson", "league_only_poisson", "expanding_league_prior"];
      const result = validateReplayDataset(dataset);
      expect(result.ok).toBe(false);
      if (!result.ok) expect(result.error).toMatch(/unexpected benchmark_scorecards\.models/);
    });

    it("rejects an overall benchmark figure that disagrees with the average of its own by-season values", () => {
      const dataset = clone(makeFullValidDataset());
      dataset.benchmark_scorecards!.overall.expanding_league_prior.log_loss = 999;
      const result = validateReplayDataset(dataset);
      expect(result.ok).toBe(false);
      if (!result.ok) expect(result.error).toMatch(/disagrees with the average of its own by-season values/);
    });

    it("rejects a team_goal_poisson benchmark entry that disagrees with season_scorecards", () => {
      const dataset = clone(makeFullValidDataset());
      const benchmark = dataset.benchmark_scorecards!;
      const other = benchmark.by_season["2025-26"].team_goal_poisson.log_loss;
      // Mutate BOTH the by-season figure and overall consistently (so the internal
      // overall-equals-average self-check still passes) to isolate the cross-check
      // against season_scorecards specifically.
      benchmark.by_season["2024-25"].team_goal_poisson.log_loss = 999;
      benchmark.overall.team_goal_poisson.log_loss = (999 + other) / 2;
      const result = validateReplayDataset(dataset);
      expect(result.ok).toBe(false);
      if (!result.ok) expect(result.error).toMatch(/disagrees with season_scorecards/);
    });

    it("rejects a benchmark model's per-season n that is not 380", () => {
      const dataset = clone(makeFullValidDataset());
      dataset.benchmark_scorecards!.by_season["2024-25"].league_only_poisson.n = 1;
      const result = validateReplayDataset(dataset);
      expect(result.ok).toBe(false);
      if (!result.ok) expect(result.error).toMatch(/is not 380/);
    });

    it("accepts the real dataset's benchmark_scorecards and its known S04 anchors", () => {
      const here = dirname(fileURLToPath(import.meta.url));
      const realPath = resolve(here, "../../public/data/replays.json");
      const raw = JSON.parse(readFileSync(realPath, "utf-8")) as ReplayDataset;
      const result = validateReplayDataset(raw);
      if (!result.ok) throw new Error(`real dataset failed validation: ${result.error}`);
      const overall = result.data.benchmark_scorecards!.overall;
      expect(overall.expanding_league_prior.log_loss).toBeCloseTo(1.0832728193824843, 9);
      expect(overall.league_only_poisson.log_loss).toBeCloseTo(1.081682047627812, 9);
      expect(overall.team_goal_poisson.log_loss).toBeCloseTo(1.0147370772418645, 9);
    });
  });

  it("never mutates a bad row into a valid-looking one — the input is untouched on rejection", () => {
    const dataset = clone(makeFullValidDataset());
    const before = JSON.stringify(dataset);
    dataset.fixtures[0].p_home = 2; // invalid
    validateReplayDataset(dataset);
    // The function must not have "fixed up" the invalid value as a side effect —
    // compare everything EXCEPT the field we deliberately broke.
    const after = JSON.parse(JSON.stringify(dataset));
    after.fixtures[0].p_home = JSON.parse(before).fixtures[0].p_home;
    expect(JSON.stringify(after)).toBe(before);
  });
});

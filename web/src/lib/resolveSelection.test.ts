import { describe, expect, it } from "vitest";
import { resolveSelection } from "./resolveSelection";
import { makeDataset, makeFixture } from "../test/fixtures";

const dataset = makeDataset({
  fixtures: [
    makeFixture({
      id: "f1",
      season: "2024-25",
      match_date: "2024-08-16",
      home_team: "Alpha FC",
      away_team: "Beta FC",
    }),
    makeFixture({
      id: "f2",
      season: "2025-26",
      match_date: "2025-08-16",
      home_team: "Gamma FC",
      away_team: "Delta FC",
    }),
  ],
  fixture_count: 2,
});

describe("resolveSelection", () => {
  it("resolves a valid season and a valid, matching fixture", () => {
    const r = resolveSelection(dataset, { season: "2024-25", fixture: "f1", team: null });
    expect(r.season).toBe("2024-25");
    expect(r.fixture?.id).toBe("f1");
    expect(r.seasonWasInvalid).toBe(false);
    expect(r.fixtureWasUnknown).toBe(false);
    expect(r.fixtureHiddenByFilter).toBe(false);
  });

  it("falls back to the first supported season and flags the link when season is unsupported", () => {
    const r = resolveSelection(dataset, { season: "garbage", fixture: null, team: null });
    expect(r.season).toBe("2024-25");
    expect(r.seasonWasInvalid).toBe(true);
    expect(r.fixture).toBeNull();
  });

  it("defaults to the first supported season (not invalid) when no season is given at all", () => {
    const r = resolveSelection(dataset, { season: null, fixture: null, team: null });
    expect(r.season).toBe("2024-25");
    expect(r.seasonWasInvalid).toBe(false);
  });

  it("flags an unknown fixture id and never returns a fixture for it", () => {
    const r = resolveSelection(dataset, { season: "2024-25", fixture: "does-not-exist", team: null });
    expect(r.fixture).toBeNull();
    expect(r.fixtureWasUnknown).toBe(true);
    expect(r.fixtureHiddenByFilter).toBe(false);
  });

  it("canonicalises a conflicting season+fixture deep link to the fixture's own real season", () => {
    // f2 is a 2025-26 fixture; the URL claims 2024-25. The fixture wins.
    const r = resolveSelection(dataset, { season: "2024-25", fixture: "f2", team: null });
    expect(r.season).toBe("2025-26");
    expect(r.fixture?.id).toBe("f2");
    expect(r.seasonWasInvalid).toBe(false);
  });

  it("hides a known fixture that the active club filter excludes, without crashing", () => {
    const r = resolveSelection(dataset, { season: "2024-25", fixture: "f1", team: "zzz-no-match" });
    expect(r.fixture).toBeNull();
    expect(r.fixtureHiddenByFilter).toBe(true);
    expect(r.fixtureWasUnknown).toBe(false);
  });

  it("keeps a fixture visible when the club filter matches it (case-insensitively, either team)", () => {
    const r1 = resolveSelection(dataset, { season: "2024-25", fixture: "f1", team: "alpha" });
    expect(r1.fixture?.id).toBe("f1");
    const r2 = resolveSelection(dataset, { season: "2024-25", fixture: "f1", team: "BETA" });
    expect(r2.fixture?.id).toBe("f1");
  });

  it("never lets a filtered-out fixture dictate the resolved season", () => {
    // f2 is 2025-26; filter excludes it; season must fall back to the validated
    // query.season (2024-25 here), not silently become 2025-26 from the hidden fixture.
    const r = resolveSelection(dataset, { season: "2024-25", fixture: "f2", team: "zzz-no-match" });
    expect(r.fixture).toBeNull();
    expect(r.season).toBe("2024-25");
  });

  it("trims whitespace from the team filter", () => {
    const r = resolveSelection(dataset, { season: "2024-25", fixture: "f1", team: "  alpha  " });
    expect(r.team).toBe("alpha");
    expect(r.fixture?.id).toBe("f1");
  });
});

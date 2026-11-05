import { describe, expect, it } from "vitest";
import { formatMatchDate, largestRemainderPercentages, seasonLabel, slugify } from "./format";

describe("largestRemainderPercentages", () => {
  it("sums to exactly 100 even when independent rounding would not", () => {
    // 48.51...% / 23.25...% / 28.24...% independently round to 49/23/28 = 100 but many
    // real triples round to 99 or 101 — assert the INVARIANT, not one lucky example.
    const cases: [number, number, number][] = [
      [0.485, 0.2325, 0.2825],
      [0.333, 0.333, 0.334],
      [0.1, 0.1, 0.8],
      [0.999, 0.0005, 0.0005],
      [0.5, 0.3, 0.2],
    ];
    for (const [h, d, a] of cases) {
      const [ph, pd, pa] = largestRemainderPercentages([h, d, a]);
      expect(ph + pd + pa).toBe(100);
      expect(ph).toBeGreaterThanOrEqual(0);
      expect(pd).toBeGreaterThanOrEqual(0);
      expect(pa).toBeGreaterThanOrEqual(0);
    }
  });

  it("keeps the largest value visibly largest in the common case", () => {
    const [ph, pd, pa] = largestRemainderPercentages([0.6, 0.25, 0.15]);
    expect(ph).toBeGreaterThan(pd);
    expect(pd).toBeGreaterThan(pa);
  });
});

describe("formatMatchDate", () => {
  it("formats an ISO date without shifting to a different calendar day", () => {
    const formatted = formatMatchDate("2024-08-16");
    expect(formatted).toContain("16");
    expect(formatted).toContain("Aug");
    expect(formatted).toContain("2024");
  });

  it("falls back to the raw string for an unparsable date rather than throwing", () => {
    expect(formatMatchDate("not-a-date")).toBe("not-a-date");
  });
});

describe("seasonLabel", () => {
  it("renders the hyphenated season code as a slash", () => {
    expect(seasonLabel("2024-25")).toBe("2024/25");
  });
});

describe("slugify", () => {
  it("lowercases and hyphenates team names", () => {
    expect(slugify("Manchester United")).toBe("manchester-united");
  });

  it("strips punctuation", () => {
    expect(slugify("Nottingham Forest F.C.")).toBe("nottingham-forest-f-c");
  });
});

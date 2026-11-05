/**
 * Converts three raw probabilities (which sum to ~1 but not always exactly, due to
 * floating-point noise) into three whole-number percentages that sum to EXACTLY 100,
 * using the largest-remainder method. This avoids the "48% + 23% + 28% = 99%" or
 * "...= 101%" artifact that naive independent rounding produces.
 */
export function largestRemainderPercentages(values: number[]): number[] {
  const scaled = values.map((v) => v * 100);
  const floors = scaled.map((v) => Math.floor(v));
  let remainder = 100 - floors.reduce((a, b) => a + b, 0);
  const remainders = scaled.map((v, i) => ({ i, frac: v - floors[i] }));
  remainders.sort((a, b) => b.frac - a.frac);
  const result = [...floors];
  for (let k = 0; k < remainders.length && remainder > 0; k++) {
    result[remainders[k].i] += 1;
    remainder--;
  }
  return result;
}

export function formatPercent(fraction: number, digits = 1): string {
  return `${(fraction * 100).toFixed(digits)}%`;
}

const DATE_FORMATTER = new Intl.DateTimeFormat("en-GB", {
  weekday: "short",
  day: "numeric",
  month: "short",
  year: "numeric",
});

export function formatMatchDate(isoDate: string): string {
  // Parsed as UTC noon to avoid local-timezone day-shift artifacts on an ISO date
  // (no time component) — this is a DATE, not a timestamp, and must never be
  // displayed as though it carries kickoff-time precision.
  const d = new Date(`${isoDate}T12:00:00Z`);
  if (Number.isNaN(d.getTime())) return isoDate;
  return DATE_FORMATTER.format(d);
}

export function seasonLabel(season: string): string {
  return season.replace("-", "/");
}

export function slugify(text: string): string {
  return text
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
}

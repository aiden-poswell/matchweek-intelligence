import type { Fixture, ReplayDataset, Season } from "../types";

export interface ResolvedSelection {
  /** Always one of dataset.evaluation_seasons — never an unvalidated pass-through. */
  season: Season;
  /** The trimmed, normalised club-name filter actually in effect. */
  team: string;
  /**
   * The fixture to display, or null. Invariant: when non-null, `fixture.season ===
   * season` AND `fixture` matches `team` — so a contradictory fixture (wrong season,
   * or excluded by the active club filter) can never be returned here. Callers must
   * never fall back to query.fixture directly for display.
   */
  fixture: Fixture | null;
  /** True when a non-empty `season` query param did not match a supported season. */
  seasonWasInvalid: boolean;
  /** True when a non-empty `fixture` query param matched no fixture in the dataset. */
  fixtureWasUnknown: boolean;
  /** True when a known, valid fixture exists but is excluded by the active club filter. */
  fixtureHiddenByFilter: boolean;
}

function matchesTeamFilter(fixture: Fixture, needle: string): boolean {
  if (needle === "") return true;
  const lower = needle.toLowerCase();
  return (
    fixture.home_team.toLowerCase().includes(lower) ||
    fixture.away_team.toLowerCase().includes(lower)
  );
}

/**
 * The single source of truth for "what should actually be on screen," computed fresh
 * from the dataset and the current URL query on every call — never incrementally
 * patched. This is what prevents the selected fixture and the active season/club
 * filter from ever diverging: there is no code path that can render a fixture whose
 * own season or club match disagrees with what is currently selected, because the
 * fixture returned here has already been checked against both.
 *
 * A fixture param that is deep-linked together with a conflicting season param is
 * resolved deterministically: the fixture's own real season wins (it is the more
 * specific, more verifiable claim), and the season shown is canonicalised to match —
 * never a silently inconsistent pairing, and never a thrown error.
 */
export function resolveSelection(
  dataset: ReplayDataset,
  query: { season: string | null; fixture: string | null; team: string | null },
): ResolvedSelection {
  const supportedSeasons = dataset.evaluation_seasons;
  const team = (query.team ?? "").trim();

  const requestedFixture = query.fixture
    ? dataset.fixtures.find((f) => f.id === query.fixture) ?? null
    : null;
  const fixtureWasUnknown = query.fixture !== null && requestedFixture === null;

  const fixtureMatchesFilter = requestedFixture ? matchesTeamFilter(requestedFixture, team) : false;
  const usableFixture = requestedFixture && fixtureMatchesFilter ? requestedFixture : null;
  const fixtureHiddenByFilter = requestedFixture !== null && !fixtureWasUnknown && usableFixture === null;

  let season: Season;
  let seasonWasInvalid = false;

  if (usableFixture) {
    // Canonicalise: a valid, filter-matching fixture always determines its own
    // season, regardless of what the URL's season param claimed.
    season = usableFixture.season;
  } else if (query.season && (supportedSeasons as string[]).includes(query.season)) {
    season = query.season as Season;
  } else {
    if (query.season) seasonWasInvalid = true;
    season = supportedSeasons[0];
  }

  return {
    season,
    team,
    fixture: usableFixture,
    seasonWasInvalid,
    fixtureWasUnknown,
    fixtureHiddenByFilter,
  };
}

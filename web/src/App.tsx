import { useEffect, useMemo, useRef, type ReactNode } from "react";
import type { Season } from "./types";
import { useReplayData } from "./lib/useReplayData";
import { useQueryState } from "./lib/queryState";
import { resolveSelection } from "./lib/resolveSelection";
import { seasonLabel } from "./lib/format";
import { Header } from "./components/Header";
import { FixturePicker } from "./components/FixturePicker";
import { FixtureDetailPanel } from "./components/FixtureDetailPanel";
import { SeasonScorecard } from "./components/SeasonScorecard";
import { Methodology } from "./components/Methodology";
import { LoadingPanel, ErrorPanel } from "./components/StatusStates";

export function App() {
  const state = useReplayData();
  const [query, setQuery] = useQueryState();

  const earliestFixture = useMemo(() => {
    if (state.status !== "ready") return null;
    return [...state.data.fixtures].sort((a, b) => a.match_date.localeCompare(b.match_date))[0];
  }, [state]);

  // A truly blank first load (no fixture AND no season in the URL at all):
  // deterministically select the chronologically earliest fixture (never
  // hand-picked for a flattering result) and its own season, recorded into the URL
  // so the state becomes a real, shareable, back/forward-navigable deep link rather
  // than silent client-only default state.
  //
  // Two conditions guard this, both load-bearing:
  //
  // `didInitialize` fires this AT MOST ONCE per app lifetime — not merely "once
  // while query.fixture happens to be empty." Without that distinction, an
  // intentional later clear of query.fixture (e.g. a season switch deliberately
  // dropping a now-wrong-season selection) would immediately be undone by this same
  // effect re-firing and snapping back to the original default fixture/season — a
  // real bug caught by App.test.tsx's season-switch regression, not a hypothetical.
  //
  // `!query.season` (not just `!query.fixture`) means this never overwrites an
  // EXPLICITLY-provided season, even an invalid one. A real-browser QA session
  // caught the bug this prevents: visiting `?view=scorecard&season=garbage` used to
  // have this effect fire anyway (since no fixture was present), silently replacing
  // "garbage" with the earliest fixture's season and injecting an unrelated fixture
  // param — which raced away the "this link's season isn't recognised" notice
  // before a visitor could ever see it. `resolveSelection` already has its own
  // correct, independent fallback for an invalid or missing season; this effect's
  // job is only to fill in a COMPLETELY blank visit, never to "fix" a season the
  // visitor (or a shared link) already specified.
  const didInitialize = useRef(false);
  useEffect(() => {
    if (state.status !== "ready" || !earliestFixture || didInitialize.current) return;
    didInitialize.current = true;
    if (!query.fixture && !query.season) {
      setQuery({ fixture: earliestFixture.id, season: earliestFixture.season });
    }
  }, [state.status, earliestFixture, query.fixture, query.season, setQuery]);

  if (state.status === "loading") {
    return (
      <Shell dataset={null} view={query.view} onViewChange={(view) => setQuery({ view })}>
        <LoadingPanel />
      </Shell>
    );
  }

  if (state.status === "error") {
    return (
      <Shell dataset={null} view={query.view} onViewChange={(view) => setQuery({ view })}>
        <ErrorPanel message={state.message} />
      </Shell>
    );
  }

  const dataset = state.data;
  const seasons = dataset.evaluation_seasons;

  // Every piece of "what's on screen" is re-derived fresh from the dataset and the
  // URL on every render — never patched incrementally — so a selected fixture can
  // never silently disagree with the active season or club filter. See
  // resolveSelection's own docstring for the exact contract.
  const resolved = resolveSelection(dataset, {
    season: query.season,
    fixture: query.fixture,
    team: query.team,
  });

  const handleSeasonChange = (season: Season) => {
    // Switching season explicitly abandons any previously selected fixture rather
    // than silently keeping a now-wrong-season fixture on screen, or guessing a
    // replacement the visitor didn't ask for.
    setQuery({ season, fixture: null });
  };

  const handleTeamChange = (team: string) => {
    // High-frequency (per-keystroke) update: replace, not push, so clearing or
    // editing a search filter doesn't spam Back-stops one character at a time.
    setQuery({ team: team || null }, { replace: true });
  };

  const handleSelectFixture = (fixtureId: string) => {
    const fixture = dataset.fixtures.find((f) => f.id === fixtureId);
    // Setting the fixture's own season explicitly (not relying solely on the
    // resolver's canonicalisation) keeps the URL itself honest for anyone who
    // copies the link.
    setQuery({ fixture: fixtureId, season: fixture?.season ?? resolved.season });
  };

  const selectedFixtureId = resolved.fixture?.id ?? null;

  return (
    <Shell dataset={dataset} view={query.view} onViewChange={(view) => setQuery({ view })}>
      {query.view === "fixtures" && (
        <>
          {resolved.seasonWasInvalid && (
            <p className="link-notice" role="status">
              The season in this link isn&rsquo;t recognised — showing{" "}
              {seasonLabel(resolved.season)} instead.
            </p>
          )}
          <div className="fixtures-layout">
            <div className="fixtures-layout__picker">
              <FixturePicker
                fixtures={dataset.fixtures}
                seasons={seasons}
                season={resolved.season}
                team={resolved.team}
                selectedFixtureId={selectedFixtureId}
                onSeasonChange={handleSeasonChange}
                onTeamChange={handleTeamChange}
                onSelectFixture={handleSelectFixture}
              />
            </div>
            <FixtureDetailPanel
              fixture={resolved.fixture}
              fixtureWasUnknown={resolved.fixtureWasUnknown}
              fixtureHiddenByFilter={resolved.fixtureHiddenByFilter}
            />
          </div>
        </>
      )}

      {query.view === "scorecard" && (
        <>
          {resolved.seasonWasInvalid && (
            <p className="link-notice" role="status">
              The season in this link isn&rsquo;t recognised — showing{" "}
              {seasonLabel(resolved.season)} instead.
            </p>
          )}
          <SeasonScorecard
            seasons={seasons}
            season={resolved.season}
            scorecards={dataset.season_scorecards}
            onSeasonChange={handleSeasonChange}
          />
        </>
      )}

      {query.view === "methodology" && <Methodology dataset={dataset} />}
    </Shell>
  );
}

function Shell({
  dataset,
  view,
  onViewChange,
  children,
}: {
  dataset: Parameters<typeof Header>[0]["dataset"];
  view: "fixtures" | "scorecard" | "methodology";
  onViewChange: (view: "fixtures" | "scorecard" | "methodology") => void;
  children: ReactNode;
}) {
  return (
    <div className="app-shell">
      <a href="#main-content" className="skip-link">
        Skip to main content
      </a>
      <Header dataset={dataset} view={view} onViewChange={onViewChange} />
      <main className="app-main" id="main-content">
        {children}
      </main>
      <footer className="site-footer">
        Historical replay only. No current or upcoming match is forecast anywhere in this
        product.
      </footer>
    </div>
  );
}

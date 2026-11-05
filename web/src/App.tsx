import { useEffect, useMemo, type ReactNode } from "react";
import type { Season } from "./types";
import { useReplayData } from "./lib/useReplayData";
import { useQueryState } from "./lib/queryState";
import { Header } from "./components/Header";
import { FixturePicker } from "./components/FixturePicker";
import { FixtureView } from "./components/FixtureView";
import { SeasonScorecard } from "./components/SeasonScorecard";
import { Methodology } from "./components/Methodology";
import { LoadingPanel, ErrorPanel, EmptyPanel } from "./components/StatusStates";

export function App() {
  const state = useReplayData();
  const [query, setQuery] = useQueryState();

  const earliestFixture = useMemo(() => {
    if (state.status !== "ready") return null;
    return [...state.data.fixtures].sort((a, b) => a.match_date.localeCompare(b.match_date))[0];
  }, [state]);

  // First load with no fixture/season in the URL: deterministically select the
  // chronologically earliest fixture (never hand-picked for a flattering result) and
  // its own season, recorded into the URL so the state becomes a real, shareable,
  // back/forward-navigable deep link rather than silent client-only default state.
  useEffect(() => {
    if (state.status !== "ready" || !earliestFixture) return;
    if (!query.fixture) {
      setQuery({ fixture: earliestFixture.id, season: earliestFixture.season });
    }
  }, [state.status, earliestFixture, query.fixture, setQuery]);

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
  const activeSeason: Season = (query.season as Season) ?? earliestFixture?.season ?? seasons[0];
  const selectedFixture = query.fixture
    ? dataset.fixtures.find((f) => f.id === query.fixture) ?? null
    : null;

  return (
    <Shell dataset={dataset} view={query.view} onViewChange={(view) => setQuery({ view })}>
      {query.view === "fixtures" && (
        <>
          <FixturePicker
            fixtures={dataset.fixtures}
            seasons={seasons}
            season={activeSeason}
            team={query.team ?? ""}
            selectedFixtureId={query.fixture}
            onSeasonChange={(season) => setQuery({ season })}
            onTeamChange={(team) => setQuery({ team: team || null })}
            onSelectFixture={(fixture) => setQuery({ fixture })}
          />
          {selectedFixture ? (
            <FixtureView fixture={selectedFixture} />
          ) : (
            <EmptyPanel message="Select a fixture from the list above to see its forecast and actual result." />
          )}
        </>
      )}

      {query.view === "scorecard" && (
        <SeasonScorecard
          seasons={seasons}
          season={activeSeason}
          scorecards={dataset.season_scorecards}
          onSeasonChange={(season) => setQuery({ season })}
        />
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
      <Header dataset={dataset} view={view} onViewChange={onViewChange} />
      <main className="app-main">{children}</main>
      <footer className="site-footer">
        Historical replay only. No current or upcoming match is forecast anywhere in this
        product.
      </footer>
    </div>
  );
}

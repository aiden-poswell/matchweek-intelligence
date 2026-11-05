import { useMemo } from "react";
import type { Fixture, Season } from "../types";
import { formatMatchDate, seasonLabel } from "../lib/format";
import { EmptyPanel } from "./StatusStates";

interface Props {
  fixtures: Fixture[];
  seasons: Season[];
  season: Season;
  team: string;
  selectedFixtureId: string | null;
  onSeasonChange: (season: Season) => void;
  onTeamChange: (team: string) => void;
  onSelectFixture: (fixtureId: string) => void;
}

export function FixturePicker({
  fixtures,
  seasons,
  season,
  team,
  selectedFixtureId,
  onSeasonChange,
  onTeamChange,
  onSelectFixture,
}: Props) {
  const filtered = useMemo(() => {
    const needle = team.trim().toLowerCase();
    return fixtures
      .filter((f) => f.season === season)
      .filter(
        (f) =>
          needle === "" ||
          f.home_team.toLowerCase().includes(needle) ||
          f.away_team.toLowerCase().includes(needle),
      )
      .sort((a, b) => a.match_date.localeCompare(b.match_date) || a.id.localeCompare(b.id));
  }, [fixtures, season, team]);

  return (
    <section aria-labelledby="fixture-picker-heading">
      <h2 id="fixture-picker-heading" className="section-label">
        Browse fixtures
      </h2>
      <div className="picker-controls">
        <div className="season-toggle" role="group" aria-label="Season">
          {seasons.map((s) => (
            <button
              key={s}
              type="button"
              aria-pressed={season === s}
              onClick={() => onSeasonChange(s)}
            >
              {seasonLabel(s)}
            </button>
          ))}
        </div>
        <div className="team-search">
          <label htmlFor="team-search-input" className="visually-hidden-label">
            Filter by club name
          </label>
          <input
            id="team-search-input"
            type="search"
            placeholder="Filter by club name…"
            value={team}
            onChange={(e) => onTeamChange(e.target.value)}
          />
        </div>
        <span className="fixture-count-note">
          {filtered.length} of {fixtures.filter((f) => f.season === season).length} fixtures
        </span>
      </div>

      {filtered.length === 0 ? (
        <EmptyPanel message="No fixtures match that club filter in this season. Try a different spelling or clear the filter." />
      ) : (
        <ul className="fixture-list" aria-label={`${seasonLabel(season)} fixtures`}>
          {filtered.map((f) => (
            <li key={f.id}>
              <button
                type="button"
                className="fixture-row"
                aria-current={f.id === selectedFixtureId}
                onClick={() => onSelectFixture(f.id)}
              >
                <span className="fixture-row__date">{formatMatchDate(f.match_date)}</span>
                <span className="fixture-row__teams">
                  {f.home_team} v {f.away_team}
                </span>
                <span className="fixture-row__score">
                  {f.home_score}–{f.away_score}
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

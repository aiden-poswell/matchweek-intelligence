import type { ReplayDataset } from "../types";

interface Props {
  dataset: ReplayDataset | null;
  view: "fixtures" | "scorecard" | "methodology";
  onViewChange: (view: "fixtures" | "scorecard" | "methodology") => void;
}

const TABS: { key: Props["view"]; label: string }[] = [
  { key: "fixtures", label: "Fixtures" },
  { key: "scorecard", label: "Season scorecard" },
  { key: "methodology", label: "Methodology & limitations" },
];

export function Header({ dataset, view, onViewChange }: Props) {
  return (
    <header className="site-header">
      <div className="site-header__inner">
        <div className="site-header__top">
          <h1 className="site-title">Matchweek Replay Lab</h1>
          <span className="replay-badge" title="This is a historical replay, not a live service">
            Replay — not live
          </span>
        </div>
        <p className="site-header__subtitle">
          A historical replay of {dataset ? dataset.fixture_count : 760} completed Premier
          League fixtures from the 2024/25 and 2025/26 seasons, scored by an independently
          documented team-goal Poisson forecasting model. Every probability shown was computed
          using results from before each match date — never from after it.
        </p>
        <div className="site-header__meta">
          {dataset && (
            <span>
              Source:{" "}
              <a
                href={`https://github.com/${dataset.source.repo}`}
                target="_blank"
                rel="noreferrer"
              >
                {dataset.source.repo}
              </a>{" "}
              ({dataset.source.license}, pinned commit)
            </span>
          )}
        </div>
        <nav className="view-tabs" aria-label="Replay Lab sections">
          {TABS.map((tab) => (
            <button
              key={tab.key}
              type="button"
              className="view-tab"
              aria-current={view === tab.key ? "page" : undefined}
              onClick={() => onViewChange(tab.key)}
            >
              {tab.label}
            </button>
          ))}
        </nav>
      </div>
    </header>
  );
}

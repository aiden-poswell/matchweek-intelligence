import { largestRemainderPercentages } from "../lib/format";

interface Props {
  pHome: number;
  pDraw: number;
  pAway: number;
  homeTeam: string;
  awayTeam: string;
}

export function ProbabilityBars({ pHome, pDraw, pAway, homeTeam, awayTeam }: Props) {
  const [pctHome, pctDraw, pctAway] = largestRemainderPercentages([pHome, pDraw, pAway]);

  const rows: { key: "home" | "draw" | "away"; label: string; pct: number }[] = [
    { key: "home", label: `${homeTeam} win`, pct: pctHome },
    { key: "draw", label: "Draw", pct: pctDraw },
    { key: "away", label: `${awayTeam} win`, pct: pctAway },
  ];

  return (
    <div
      className="prob-bars"
      role="group"
      aria-label="Pre-match outcome probabilities, home win, draw, away win, summing to 100 percent"
    >
      {rows.map((row) => (
        <div className="prob-bar-row" key={row.key}>
          <span className="prob-bar-row__label">{row.label}</span>
          <div
            className="prob-bar-track"
            role="img"
            aria-label={`${row.label}: ${row.pct} percent`}
          >
            <div
              className={`prob-bar-fill prob-bar-fill--${row.key}`}
              style={{ width: `${row.pct}%` }}
            />
          </div>
          <span className="prob-bar-row__value">{row.pct}%</span>
        </div>
      ))}
    </div>
  );
}

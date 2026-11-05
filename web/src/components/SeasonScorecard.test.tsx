import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { SeasonScorecard } from "./SeasonScorecard";
import { makeDataset } from "../test/fixtures";

describe("SeasonScorecard", () => {
  const dataset = makeDataset();

  it("shows N and the three proper scores for the selected season", () => {
    render(
      <SeasonScorecard
        seasons={dataset.evaluation_seasons}
        season="2024-25"
        scorecards={dataset.season_scorecards}
        onSeasonChange={vi.fn()}
      />,
    );
    expect(screen.getByText(/N = 2 evaluated fixtures/)).toBeInTheDocument();
    expect(screen.getByText("0.9900")).toBeInTheDocument(); // log loss
    expect(screen.getByText("0.6000")).toBeInTheDocument(); // brier
    expect(screen.getByText("0.2000")).toBeInTheDocument(); // rps
  });

  it("switches to the other season's figures when selected", () => {
    render(
      <SeasonScorecard
        seasons={dataset.evaluation_seasons}
        season="2025-26"
        scorecards={dataset.season_scorecards}
        onSeasonChange={vi.fn()}
      />,
    );
    expect(screen.getByText(/N = 1 evaluated fixtures/)).toBeInTheDocument();
    expect(screen.getByText("1.0200")).toBeInTheDocument();
  });

  it("formats a negative draw-calibration gap with an explicit minus sign", () => {
    render(
      <SeasonScorecard
        seasons={dataset.evaluation_seasons}
        season="2025-26"
        scorecards={dataset.season_scorecards}
        onSeasonChange={vi.fn()}
      />,
    );
    expect(screen.getByText("-3.00 pp")).toBeInTheDocument();
  });

  it("formats a positive draw-calibration gap with an explicit plus sign", () => {
    render(
      <SeasonScorecard
        seasons={dataset.evaluation_seasons}
        season="2024-25"
        scorecards={dataset.season_scorecards}
        onSeasonChange={vi.fn()}
      />,
    );
    expect(screen.getByText("+3.00 pp")).toBeInTheDocument();
  });
});

import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { SeasonScorecard } from "./SeasonScorecard";
import { makeDataset, makeFullValidDataset } from "../test/fixtures";

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

  it("shows no benchmark comparison when the dataset has none (optional, additive section)", () => {
    render(
      <SeasonScorecard
        seasons={dataset.evaluation_seasons}
        season="2024-25"
        scorecards={dataset.season_scorecards}
        onSeasonChange={vi.fn()}
      />,
    );
    expect(screen.queryByText(/why team-goal poisson/i)).not.toBeInTheDocument();
  });

  it("shows the three-baseline benchmark comparison, labelling the adopted model, when supplied", () => {
    const full = makeFullValidDataset();
    render(
      <SeasonScorecard
        seasons={full.evaluation_seasons}
        season="2024-25"
        scorecards={full.season_scorecards}
        benchmark={full.benchmark_scorecards}
        onSeasonChange={vi.fn()}
      />,
    );
    expect(screen.getByText(/why team-goal poisson/i)).toBeInTheDocument();
    expect(screen.getByText(/Team-goal Poisson \(adopted default\)/)).toBeInTheDocument();
    expect(screen.getByText(/Expanding league prior/)).toBeInTheDocument();
    expect(screen.getByText(/League-only Poisson/)).toBeInTheDocument();
    // the adopted model's displayed figure must be the real, independently-sourced
    // season figure, not a hand-typed or re-rounded duplicate
    const expectedLogLoss = full.benchmark_scorecards!.by_season["2024-25"].team_goal_poisson.log_loss.toFixed(4);
    expect(screen.getAllByText(expectedLogLoss).length).toBeGreaterThan(0);
  });

  it("never claims a prospective guarantee or an untouched holdout in the benchmark disclosure", () => {
    const full = makeFullValidDataset();
    render(
      <SeasonScorecard
        seasons={full.evaluation_seasons}
        season="2024-25"
        scorecards={full.season_scorecards}
        benchmark={full.benchmark_scorecards}
        onSeasonChange={vi.fn()}
      />,
    );
    expect(screen.queryByText(/guarantee/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/untouched/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/holdout/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/betting|odds|value bet/i)).not.toBeInTheDocument();
  });
});

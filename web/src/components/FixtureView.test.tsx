import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { FixtureView } from "./FixtureView";
import { makeFixture } from "../test/fixtures";

describe("FixtureView", () => {
  it("never claims the forecast existed before this result existed (S08 timing fix)", () => {
    render(<FixtureView fixture={makeFixture()} />);
    expect(
      screen.queryByText(/pre-match forecast/i, { exact: false }),
    ).not.toBeInTheDocument();
    expect(screen.queryByText(/computed before this result existed/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/available at kickoff/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/recorded pre-kickoff/i)).not.toBeInTheDocument();
  });

  it("labels the forecast as a retrospective historical replay, not a prospective prediction", () => {
    render(<FixtureView fixture={makeFixture()} />);
    expect(
      screen.getByText(/historical forecast replay/i, { exact: false }),
    ).toBeInTheDocument();
    expect(screen.getByText(/calculated after the match/i, { exact: false })).toBeInTheDocument();
  });

  it("keeps the actual final score clearly separate from the retrospective forecast", () => {
    render(
      <FixtureView
        fixture={makeFixture({ home_score: 3, away_score: 1, actual_outcome: "H" })}
      />,
    );
    expect(screen.getByText("Actual full-time result")).toBeInTheDocument();
    expect(screen.getByText("3–1")).toBeInTheDocument();
    expect(screen.getByText(/historical forecast replay/i, { exact: false })).toBeInTheDocument();
  });

  it("states the forecast used only results from before the match date, without claiming it was issued in advance", () => {
    render(<FixtureView fixture={makeFixture()} />);
    expect(
      screen.getByText(/never issued before kickoff/i, { exact: false }),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/could not have been issued publicly in advance/i, { exact: false }),
    ).toBeInTheDocument();
  });
});

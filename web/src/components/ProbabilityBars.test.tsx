import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { ProbabilityBars } from "./ProbabilityBars";

describe("ProbabilityBars", () => {
  it("labels each bar with the team names and shows percentages summing to 100", () => {
    render(
      <ProbabilityBars pHome={0.485} pDraw={0.2325} pAway={0.2825} homeTeam="Alpha FC" awayTeam="Beta FC" />,
    );
    expect(screen.getByText(/Alpha FC win/)).toBeInTheDocument();
    expect(screen.getByText("Draw")).toBeInTheDocument();
    expect(screen.getByText(/Beta FC win/)).toBeInTheDocument();

    const values = screen.getAllByText(/^\d+%$/).map((el) => parseInt(el.textContent ?? "0", 10));
    expect(values).toHaveLength(3);
    expect(values.reduce((a, b) => a + b, 0)).toBe(100);
  });

  it("never shows outcomes out of home/draw/away order", () => {
    render(<ProbabilityBars pHome={0.5} pDraw={0.3} pAway={0.2} homeTeam="X" awayTeam="Y" />);
    const labels = screen
      .getAllByText(/win|Draw/)
      .map((el) => el.textContent);
    expect(labels).toEqual(["X win", "Draw", "Y win"]);
  });
});

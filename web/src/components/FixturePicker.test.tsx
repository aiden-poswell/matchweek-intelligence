import { describe, expect, it, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { FixturePicker } from "./FixturePicker";
import { makeFixture } from "../test/fixtures";

const fixtures = [
  makeFixture({ id: "f1", season: "2024-25", home_team: "Alpha FC", away_team: "Beta FC", match_date: "2024-08-16" }),
  makeFixture({ id: "f2", season: "2024-25", home_team: "Gamma FC", away_team: "Delta FC", match_date: "2024-09-01" }),
  makeFixture({ id: "f3", season: "2025-26", home_team: "Alpha FC", away_team: "Gamma FC", match_date: "2025-08-16" }),
];

describe("FixturePicker", () => {
  it("only shows fixtures from the selected season", () => {
    render(
      <FixturePicker
        fixtures={fixtures}
        seasons={["2024-25", "2025-26"]}
        season="2024-25"
        team=""
        selectedFixtureId={null}
        onSeasonChange={vi.fn()}
        onTeamChange={vi.fn()}
        onSelectFixture={vi.fn()}
      />,
    );
    expect(screen.getByText(/Alpha FC v Beta FC/)).toBeInTheDocument();
    expect(screen.getByText(/Gamma FC v Delta FC/)).toBeInTheDocument();
    expect(screen.queryByText(/Alpha FC v Gamma FC/)).not.toBeInTheDocument();
  });

  it("filters fixtures by club name search, case-insensitively", () => {
    render(
      <FixturePicker
        fixtures={fixtures}
        seasons={["2024-25", "2025-26"]}
        season="2024-25"
        team="gamma"
        selectedFixtureId={null}
        onSeasonChange={vi.fn()}
        onTeamChange={vi.fn()}
        onSelectFixture={vi.fn()}
      />,
    );
    expect(screen.queryByText(/Alpha FC v Beta FC/)).not.toBeInTheDocument();
    expect(screen.getByText(/Gamma FC v Delta FC/)).toBeInTheDocument();
  });

  it("shows an empty state, not a blank list, when no fixture matches the filter", () => {
    render(
      <FixturePicker
        fixtures={fixtures}
        seasons={["2024-25", "2025-26"]}
        season="2024-25"
        team="nonexistent-club-xyz"
        selectedFixtureId={null}
        onSeasonChange={vi.fn()}
        onTeamChange={vi.fn()}
        onSelectFixture={vi.fn()}
      />,
    );
    expect(screen.getByText(/No fixtures match/)).toBeInTheDocument();
  });

  it("calls onSelectFixture with the fixture id when a row is clicked", () => {
    const onSelectFixture = vi.fn();
    render(
      <FixturePicker
        fixtures={fixtures}
        seasons={["2024-25", "2025-26"]}
        season="2024-25"
        team=""
        selectedFixtureId={null}
        onSeasonChange={vi.fn()}
        onTeamChange={vi.fn()}
        onSelectFixture={onSelectFixture}
      />,
    );
    fireEvent.click(screen.getByText(/Alpha FC v Beta FC/));
    expect(onSelectFixture).toHaveBeenCalledWith("f1");
  });

  it("calls onSeasonChange when a season toggle button is clicked", () => {
    const onSeasonChange = vi.fn();
    render(
      <FixturePicker
        fixtures={fixtures}
        seasons={["2024-25", "2025-26"]}
        season="2024-25"
        team=""
        selectedFixtureId={null}
        onSeasonChange={onSeasonChange}
        onTeamChange={vi.fn()}
        onSelectFixture={vi.fn()}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: "2025/26" }));
    expect(onSeasonChange).toHaveBeenCalledWith("2025-26");
  });

  it("marks the selected fixture row with aria-current", () => {
    render(
      <FixturePicker
        fixtures={fixtures}
        seasons={["2024-25", "2025-26"]}
        season="2024-25"
        team=""
        selectedFixtureId="f2"
        onSeasonChange={vi.fn()}
        onTeamChange={vi.fn()}
        onSelectFixture={vi.fn()}
      />,
    );
    const selectedRow = screen.getByText(/Gamma FC v Delta FC/).closest("button");
    expect(selectedRow).toHaveAttribute("aria-current", "true");
  });
});

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import { FixtureDetailPanel } from "./FixtureDetailPanel";
import { makeFixture } from "../test/fixtures";

const fixtureA = makeFixture();
const fixtureB = makeFixture({
  id: "f2",
  home_team: "Gamma FC",
  away_team: "Delta FC",
  match_date: "2024-09-01",
});

function mockRect(partial: Partial<DOMRect>) {
  return {
    top: 0,
    bottom: 0,
    left: 0,
    right: 0,
    width: 0,
    height: 0,
    x: 0,
    y: 0,
    toJSON: () => ({}),
    ...partial,
  } as DOMRect;
}

// jsdom does not implement scrollIntoView at all (not even as a no-op) — define it
// once so vi.spyOn has a real method on the prototype to spy on.
if (!HTMLElement.prototype.scrollIntoView) {
  HTMLElement.prototype.scrollIntoView = () => {};
}

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

beforeEach(() => {
  Object.defineProperty(window, "innerHeight", { value: 800, configurable: true });
});

describe("FixtureDetailPanel", () => {
  it("never scrolls or steals focus for the very first (initial/default) fixture", () => {
    const scrollSpy = vi
      .spyOn(HTMLElement.prototype, "scrollIntoView")
      .mockImplementation(() => {});
    vi.spyOn(HTMLElement.prototype, "getBoundingClientRect").mockReturnValue(
      mockRect({ top: 2000, bottom: 2400 }), // clearly off-screen
    );

    render(
      <FixtureDetailPanel fixture={fixtureA} fixtureWasUnknown={false} fixtureHiddenByFilter={false} />,
    );

    expect(scrollSpy).not.toHaveBeenCalled();
  });

  it("scrolls and moves focus to the panel when a SUBSEQUENT selection lands off-screen", () => {
    vi.spyOn(HTMLElement.prototype, "getBoundingClientRect").mockReturnValue(
      mockRect({ top: 2000, bottom: 2400 }),
    );
    const scrollSpy = vi
      .spyOn(HTMLElement.prototype, "scrollIntoView")
      .mockImplementation(() => {});

    const { rerender } = render(
      <FixtureDetailPanel fixture={fixtureA} fixtureWasUnknown={false} fixtureHiddenByFilter={false} />,
    );
    expect(scrollSpy).not.toHaveBeenCalled(); // first selection — not yet

    rerender(
      <FixtureDetailPanel fixture={fixtureB} fixtureWasUnknown={false} fixtureHiddenByFilter={false} />,
    );

    expect(scrollSpy).toHaveBeenCalledTimes(1);
    const panel = screen.getByRole("heading", { name: /Gamma FC.*Delta FC/ }).closest(
      ".fixtures-layout__detail",
    );
    expect(panel).toHaveFocus();
  });

  it("does not scroll or steal focus when the panel is already fully on screen (e.g. the desktop two-column layout)", () => {
    vi.spyOn(HTMLElement.prototype, "getBoundingClientRect").mockReturnValue(
      mockRect({ top: 100, bottom: 400 }), // within the 0..800 viewport
    );
    const scrollSpy = vi
      .spyOn(HTMLElement.prototype, "scrollIntoView")
      .mockImplementation(() => {});

    const { rerender } = render(
      <FixtureDetailPanel fixture={fixtureA} fixtureWasUnknown={false} fixtureHiddenByFilter={false} />,
    );
    rerender(
      <FixtureDetailPanel fixture={fixtureB} fixtureWasUnknown={false} fixtureHiddenByFilter={false} />,
    );

    expect(scrollSpy).not.toHaveBeenCalled();
  });

  it("does not re-trigger when re-rendered with the same fixture", () => {
    vi.spyOn(HTMLElement.prototype, "getBoundingClientRect").mockReturnValue(
      mockRect({ top: 2000, bottom: 2400 }),
    );
    const scrollSpy = vi
      .spyOn(HTMLElement.prototype, "scrollIntoView")
      .mockImplementation(() => {});

    const { rerender } = render(
      <FixtureDetailPanel fixture={fixtureA} fixtureWasUnknown={false} fixtureHiddenByFilter={false} />,
    );
    rerender(
      <FixtureDetailPanel fixture={fixtureB} fixtureWasUnknown={false} fixtureHiddenByFilter={false} />,
    );
    scrollSpy.mockClear();
    rerender(
      <FixtureDetailPanel fixture={fixtureB} fixtureWasUnknown={false} fixtureHiddenByFilter={false} />,
    );

    expect(scrollSpy).not.toHaveBeenCalled();
  });

  it("is not a focus trap: the panel's own tabIndex is -1 (programmatic focus only, not in the Tab order)", () => {
    render(
      <FixtureDetailPanel fixture={fixtureA} fixtureWasUnknown={false} fixtureHiddenByFilter={false} />,
    );
    const panel = screen.getByRole("heading", { name: /Alpha FC.*Beta FC/ }).closest(
      ".fixtures-layout__detail",
    );
    expect(panel).toHaveAttribute("tabindex", "-1");
  });

  it("shows the correct empty state when no fixture is selected", () => {
    render(<FixtureDetailPanel fixture={null} fixtureWasUnknown={false} fixtureHiddenByFilter={false} />);
    expect(screen.getByText(/Select a fixture from the list above/)).toBeInTheDocument();
  });
});

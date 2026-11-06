import { useEffect, useRef } from "react";
import type { Fixture } from "../types";
import { FixtureView } from "./FixtureView";
import { EmptyPanel } from "./StatusStates";

interface Props {
  fixture: Fixture | null;
  fixtureWasUnknown: boolean;
  fixtureHiddenByFilter: boolean;
}

/**
 * On a desktop-width viewport this panel sits beside the fixture list (see the
 * `.fixtures-layout` two-column grid in styles.css), so it is already fully visible
 * the moment a fixture is selected — nothing needs to move. On a narrow viewport the
 * two stack vertically and the list can be taller than the screen, so a selection can
 * land below the fold with no visible sign anything happened. This component checks
 * the panel's own actual on-screen position (not a viewport-width breakpoint — a
 * tall picker or an unusual zoom level can push it off-screen even on a wide screen)
 * and only then scrolls it into view and moves keyboard focus there.
 *
 * This is NOT a focus trap: focus lands here once, and Tab/Shift+Tab continue
 * completely normally afterwards. It also never fires on the very first (often
 * programmatic, default-selection) fixture, so page load never steals focus away
 * from wherever the visitor actually started.
 */
export function FixtureDetailPanel({ fixture, fixtureWasUnknown, fixtureHiddenByFilter }: Props) {
  const panelRef = useRef<HTMLDivElement | null>(null);
  const lastFixtureId = useRef<string | null>(null);

  useEffect(() => {
    if (!fixture || fixture.id === lastFixtureId.current) return;
    const isFirstSelection = lastFixtureId.current === null;
    lastFixtureId.current = fixture.id;
    if (isFirstSelection) return;

    const el = panelRef.current;
    if (!el) return;
    const rect = el.getBoundingClientRect();
    const fullyVisible = rect.top >= 0 && rect.bottom <= window.innerHeight;
    if (fullyVisible) return;

    const prefersReducedMotion =
      window.matchMedia?.("(prefers-reduced-motion: reduce)").matches ?? false;
    el.scrollIntoView({ behavior: prefersReducedMotion ? "auto" : "smooth", block: "start" });
    el.focus({ preventScroll: true });
  }, [fixture]);

  return (
    <div
      ref={panelRef}
      className="fixtures-layout__detail"
      tabIndex={-1}
      aria-label={
        fixture ? `Selected fixture: ${fixture.home_team} v ${fixture.away_team}` : undefined
      }
    >
      {fixture ? (
        <FixtureView fixture={fixture} />
      ) : fixtureWasUnknown ? (
        <EmptyPanel message="This fixture link doesn't match any fixture in this dataset. Pick a fixture from the list above." />
      ) : fixtureHiddenByFilter ? (
        <EmptyPanel message="The previously selected fixture doesn't match the current club filter. Clear the filter or pick another fixture from the list above." />
      ) : (
        <EmptyPanel message="Select a fixture from the list above to see its forecast and actual result." />
      )}
    </div>
  );
}

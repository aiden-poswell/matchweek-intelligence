import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor, fireEvent, cleanup } from "@testing-library/react";
import React from "react";
import { App } from "./App";
import { makeFullValidDataset } from "./test/fixtures";

// App.test.tsx renders the real <App/>, so the fetched dataset must pass the real
// browser-side validateReplayDataset contract (exactly 760 fixtures, 380/season,
// reconciling scorecards) — see test/fixtures.ts's makeFullValidDataset docstring.
const dataset = makeFullValidDataset();

function mockFetchOnce() {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(dataset),
    }),
  );
}

beforeEach(() => {
  window.history.replaceState(null, "", "/");
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("App", () => {
  it("shows a loading state, then the chronologically earliest fixture by default", async () => {
    mockFetchOnce();
    render(<App />);
    expect(screen.getByText(/Loading historical fixture data/)).toBeInTheDocument();

    // Wait for the REAL thing we care about (the heading), not a weaker proxy like
    // "some fixture row text is visible" — the fixture list renders as soon as the
    // dataset is ready, before the default-selection effect has necessarily flushed,
    // so a weaker wait condition can resolve on that earlier, pre-selection render
    // and make the next assertion flaky under load (reproduced directly: this test
    // intermittently failed when run alongside other test files with the weaker
    // wait, and passed reliably once changed to wait on the heading itself).
    await waitFor(() => {
      expect(screen.getByRole("heading", { name: /Alpha FC.*Beta FC/ })).toBeInTheDocument();
    });
    expect(window.location.search).toContain("fixture=2024-08-16--alpha-fc--vs--beta-fc");
  });

  it("shows an honest error state and no fabricated data when the fetch fails", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: false, status: 404 }));
    render(<App />);
    await waitFor(() => {
      expect(screen.getByText(/Unable to load historical fixture data/)).toBeInTheDocument();
    });
    expect(screen.getByText(/No placeholder or illustrative data/)).toBeInTheDocument();
  });

  it("hydrates the selected fixture directly from a deep-linked URL", async () => {
    window.history.replaceState(
      null,
      "",
      "/?fixture=2024-09-01--gamma-fc--vs--delta-fc&season=2024-25",
    );
    mockFetchOnce();
    render(<App />);
    await waitFor(() => {
      expect(screen.getByRole("heading", { name: /Gamma FC.*Delta FC/ })).toBeInTheDocument();
    });
  });

  // --- (a) season toggle from a selected fixture ------------------------------------

  it("(a) switching season clears a now-wrong-season selection rather than showing it anyway", async () => {
    mockFetchOnce();
    render(<App />);
    await waitFor(() => {
      expect(screen.getByRole("heading", { name: /Alpha FC.*Beta FC/ })).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("button", { name: "2025/26" }));

    await waitFor(() => {
      // The 2024/25 fixture must never remain displayed under the 2025/26 filter.
      expect(screen.queryByRole("heading", { name: /Alpha FC.*Beta FC/ })).not.toBeInTheDocument();
      expect(screen.queryByText(/Alpha FC v Beta FC/)).not.toBeInTheDocument();
      expect(screen.getByText(/Alpha FC v Gamma FC/)).toBeInTheDocument();
      expect(screen.getByText(/Select a fixture from the list above/)).toBeInTheDocument();
    });
    expect(window.location.search).not.toContain("fixture=2024-08-16");
  });

  // --- (b) club filter from a selected fixture ---------------------------------------

  it("(b) a club filter that excludes the selected fixture hides it with an honest message, and shows it again once cleared", async () => {
    mockFetchOnce();
    render(<App />);
    await waitFor(() => {
      expect(screen.getByRole("heading", { name: /Alpha FC.*Beta FC/ })).toBeInTheDocument();
    });

    fireEvent.change(screen.getByLabelText("Filter by club name"), {
      target: { value: "Gamma" },
    });

    await waitFor(() => {
      expect(screen.queryByRole("heading", { name: /Alpha FC.*Beta FC/ })).not.toBeInTheDocument();
      expect(screen.getByText(/doesn't match the current club filter/)).toBeInTheDocument();
    });

    fireEvent.change(screen.getByLabelText("Filter by club name"), { target: { value: "" } });
    await waitFor(() => {
      expect(screen.getByRole("heading", { name: /Alpha FC.*Beta FC/ })).toBeInTheDocument();
    });
  });

  // --- (c) zero-result filter ---------------------------------------------------------

  it("(c) a club filter matching no fixture shows the empty-filter state, not a blank or crashed screen", async () => {
    mockFetchOnce();
    render(<App />);
    await waitFor(() => {
      expect(screen.getByRole("heading", { name: /Alpha FC.*Beta FC/ })).toBeInTheDocument();
    });

    fireEvent.change(screen.getByLabelText("Filter by club name"), {
      target: { value: "zzz-no-such-club" },
    });

    await waitFor(() => {
      expect(screen.getByText(/No fixtures match that club filter/)).toBeInTheDocument();
    });
  });

  // --- (d) malformed season scorecard link --------------------------------------------

  it("(d) an unsupported season on the scorecard view falls back safely instead of crashing", async () => {
    window.history.replaceState(null, "", "/?view=scorecard&season=garbage");
    mockFetchOnce();
    render(<App />);

    await waitFor(() => {
      expect(screen.getByText(/isn.t recognised/)).toBeInTheDocument();
      expect(screen.getByText(/N = 380 evaluated fixtures/)).toBeInTheDocument();
    });
  });

  // --- (e) conflicting season+fixture deep link ----------------------------------------

  it("(e) a fixture deep-linked with the wrong season is resolved to the fixture's own real season", async () => {
    // f3 ("Alpha FC v Gamma FC") is a 2025-26 fixture; the URL below wrongly claims
    // 2024-25. The fixture's real season must win, transparently, with no crash.
    window.history.replaceState(
      null,
      "",
      "/?fixture=2025-08-16--alpha-fc--vs--gamma-fc&season=2024-25",
    );
    mockFetchOnce();
    render(<App />);

    await waitFor(() => {
      expect(screen.getByRole("heading", { name: /Alpha FC.*Gamma FC/ })).toBeInTheDocument();
    });
    expect(screen.getByRole("button", { name: "2025/26" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
  });

  // --- (f) unknown fixture link ----------------------------------------------------------

  it("(f) an unknown fixture id never silently shows unrelated data", async () => {
    window.history.replaceState(null, "", "/?fixture=this-fixture-id-does-not-exist");
    mockFetchOnce();
    render(<App />);

    await waitFor(() => {
      expect(screen.getByText(/doesn't match any fixture in this dataset/)).toBeInTheDocument();
    });
    expect(screen.queryByRole("heading", { name: /v/ })).not.toBeInTheDocument();
  });

  // --- (g) Back AND Forward through changed filters ---------------------------------------

  it("(g) browser Back and Forward both work across a season switch", async () => {
    mockFetchOnce();
    render(<App />);
    await waitFor(() => {
      expect(screen.getByRole("heading", { name: /Alpha FC.*Beta FC/ })).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("button", { name: "2025/26" }));
    await waitFor(() => {
      expect(screen.getByText(/Alpha FC v Gamma FC/)).toBeInTheDocument();
      expect(screen.queryByText(/Alpha FC v Beta FC/)).not.toBeInTheDocument();
    });

    window.history.back();
    await waitFor(() => {
      expect(screen.getByRole("heading", { name: /Alpha FC.*Beta FC/ })).toBeInTheDocument();
    });

    window.history.forward();
    await waitFor(() => {
      expect(screen.getByText(/Alpha FC v Gamma FC/)).toBeInTheDocument();
      expect(screen.queryByText(/Alpha FC v Beta FC/)).not.toBeInTheDocument();
    });
  });

  it("supports browser Back navigation between two selected fixtures", async () => {
    mockFetchOnce();
    render(<App />);
    await waitFor(() => {
      expect(screen.getByRole("heading", { name: /Alpha FC.*Beta FC/ })).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText(/Gamma FC v Delta FC/));
    await waitFor(() => {
      expect(screen.getByRole("heading", { name: /Gamma FC.*Delta FC/ })).toBeInTheDocument();
    });

    window.history.back();
    await waitFor(() => {
      expect(screen.getByRole("heading", { name: /Alpha FC.*Beta FC/ })).toBeInTheDocument();
    });
  });

  it("switching to the scorecard view and back preserves the selected fixture", async () => {
    mockFetchOnce();
    render(<App />);
    await waitFor(() => {
      expect(screen.getByRole("heading", { name: /Alpha FC.*Beta FC/ })).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("button", { name: "Season scorecard" }));
    await waitFor(() => expect(screen.getByText(/N = 380 evaluated fixtures/)).toBeInTheDocument());

    fireEvent.click(screen.getByRole("button", { name: "Fixtures" }));
    await waitFor(() => {
      expect(screen.getByRole("heading", { name: /Alpha FC.*Beta FC/ })).toBeInTheDocument();
    });
  });

  // --- (h) React.StrictMode history behavior ------------------------------------------

  it("(h) under React.StrictMode, one click still produces exactly one history transition", async () => {
    mockFetchOnce();
    const pushSpy = vi.spyOn(window.history, "pushState");
    render(
      <React.StrictMode>
        <App />
      </React.StrictMode>,
    );

    await waitFor(() => {
      expect(screen.getByRole("heading", { name: /Alpha FC.*Beta FC/ })).toBeInTheDocument();
    });
    const callsAfterInitialLoad = pushSpy.mock.calls.length;

    fireEvent.click(screen.getByText(/Gamma FC v Delta FC/));
    await waitFor(() => {
      expect(screen.getByRole("heading", { name: /Gamma FC.*Delta FC/ })).toBeInTheDocument();
    });

    // Exactly one additional history transition for exactly one click — StrictMode's
    // deliberate double-invocation of effects/updaters must not duplicate it.
    expect(pushSpy.mock.calls.length - callsAfterInitialLoad).toBe(1);
    pushSpy.mockRestore();
  });
});

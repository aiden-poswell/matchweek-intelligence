import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor, fireEvent, cleanup } from "@testing-library/react";
import { App } from "./App";
import { makeDataset } from "./test/fixtures";

const dataset = makeDataset();

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

    await waitFor(() => {
      expect(screen.getByText(/Alpha FC/)).toBeInTheDocument();
    });
    // The earliest fixture in the synthetic dataset is 2024-08-16 Alpha FC v Beta FC.
    expect(screen.getByRole("heading", { name: /Alpha FC.*Beta FC/ })).toBeInTheDocument();
    expect(window.location.search).toContain("fixture=2024-08-16--alpha-fc--vs--beta-fc");
  });

  it("shows an honest error state and no fabricated data when the fetch fails", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({ ok: false, status: 404 }),
    );
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

  it("switching season tabs updates the fixture list without reloading data", async () => {
    mockFetchOnce();
    render(<App />);
    await waitFor(() => expect(screen.getByText(/Alpha FC v Beta FC/)).toBeInTheDocument());

    fireEvent.click(screen.getByRole("button", { name: "2025/26" }));
    await waitFor(() => {
      expect(screen.queryByText(/Alpha FC v Beta FC/)).not.toBeInTheDocument();
      expect(screen.getByText(/Alpha FC v Gamma FC/)).toBeInTheDocument();
    });
  });

  it("supports browser Back navigation between two selected fixtures", async () => {
    mockFetchOnce();
    render(<App />);
    await waitFor(() => expect(screen.getByText(/Alpha FC v Beta FC/)).toBeInTheDocument());

    fireEvent.click(screen.getByText(/Gamma FC v Delta FC/));
    await waitFor(() => {
      expect(screen.getByRole("heading", { name: /Gamma FC.*Delta FC/ })).toBeInTheDocument();
    });

    // Simulate the browser's Back button: pop to the previous history entry and fire
    // the popstate event the real browser would dispatch.
    window.history.back();
    await waitFor(() => {
      expect(screen.getByRole("heading", { name: /Alpha FC.*Beta FC/ })).toBeInTheDocument();
    });
  });

  it("switching to the scorecard view and back preserves the selected fixture", async () => {
    mockFetchOnce();
    render(<App />);
    await waitFor(() => expect(screen.getByText(/Alpha FC v Beta FC/)).toBeInTheDocument());

    fireEvent.click(screen.getByRole("button", { name: "Season scorecard" }));
    await waitFor(() => expect(screen.getByText(/N = 2 evaluated fixtures/)).toBeInTheDocument());

    fireEvent.click(screen.getByRole("button", { name: "Fixtures" }));
    await waitFor(() => {
      expect(screen.getByRole("heading", { name: /Alpha FC.*Beta FC/ })).toBeInTheDocument();
    });
  });
});

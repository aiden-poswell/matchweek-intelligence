import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { act, render, cleanup, waitFor } from "@testing-library/react";
import { useQueryState } from "./queryState";

function Harness({ onReady }: { onReady: (api: ReturnType<typeof useQueryState>) => void }) {
  const api = useQueryState();
  onReady(api);
  return null;
}

beforeEach(() => {
  window.history.replaceState(null, "", "/");
});

afterEach(() => {
  cleanup();
});

describe("useQueryState", () => {
  it("one setQuery call produces exactly one pushState call", () => {
    let api: ReturnType<typeof useQueryState> | null = null;
    render(<Harness onReady={(a) => (api = a)} />);
    const pushSpy = vi.spyOn(window.history, "pushState");

    act(() => {
      api![1]({ fixture: "abc" });
    });

    expect(pushSpy).toHaveBeenCalledTimes(1);
    expect(window.location.search).toContain("fixture=abc");
    pushSpy.mockRestore();
  });

  it("{ replace: true } uses replaceState and never pushState", () => {
    let api: ReturnType<typeof useQueryState> | null = null;
    render(<Harness onReady={(a) => (api = a)} />);
    const pushSpy = vi.spyOn(window.history, "pushState");
    const replaceSpy = vi.spyOn(window.history, "replaceState");

    act(() => {
      api![1]({ team: "arsenal" }, { replace: true });
    });

    expect(pushSpy).not.toHaveBeenCalled();
    expect(replaceSpy).toHaveBeenCalledTimes(1);
    expect(window.location.search).toContain("team=arsenal");
    pushSpy.mockRestore();
    replaceSpy.mockRestore();
  });

  it("merges onto the latest committed query, not a stale snapshot, across rapid sequential calls", () => {
    let api: ReturnType<typeof useQueryState> | null = null;
    render(<Harness onReady={(a) => (api = a)} />);

    act(() => {
      api![1]({ season: "2024-25" });
    });
    act(() => {
      api![1]({ fixture: "xyz" });
    });

    // Both updates must be present together — a stale-snapshot bug would have the
    // second call overwrite the first instead of merging onto it.
    expect(window.location.search).toContain("season=2024-25");
    expect(window.location.search).toContain("fixture=xyz");
  });

  it("a real popstate event (e.g. the browser Back button) is reflected in the next render", async () => {
    let api: ReturnType<typeof useQueryState> | null = null;
    render(<Harness onReady={(a) => (api = a)} />);

    act(() => {
      api![1]({ fixture: "first" });
    });
    act(() => {
      api![1]({ fixture: "second" });
    });
    expect(window.location.search).toContain("fixture=second");

    // jsdom's history.back() queues its own popstate dispatch asynchronously (it is
    // a real session-history traversal, not a synchronous call) — await it via
    // waitFor rather than assuming a single synchronous act() flush is enough.
    window.history.back();
    await waitFor(() => {
      expect(api![0].fixture).toBe("first");
    });
  });

  it("does not call pushState or replaceState at all when the hook merely mounts", () => {
    const pushSpy = vi.spyOn(window.history, "pushState");
    const replaceSpy = vi.spyOn(window.history, "replaceState");
    render(<Harness onReady={() => {}} />);
    expect(pushSpy).not.toHaveBeenCalled();
    expect(replaceSpy).not.toHaveBeenCalled();
    pushSpy.mockRestore();
    replaceSpy.mockRestore();
  });
});

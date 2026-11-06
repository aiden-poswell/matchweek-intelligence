import { useCallback, useEffect, useRef, useState } from "react";

export interface AppQuery {
  view: "fixtures" | "scorecard" | "methodology";
  season: string | null;
  fixture: string | null;
  team: string | null;
}

const DEFAULT_QUERY: AppQuery = { view: "fixtures", season: null, fixture: null, team: null };

function parseQuery(search: string): AppQuery {
  const params = new URLSearchParams(search);
  const view = params.get("view");
  return {
    view: view === "scorecard" || view === "methodology" ? view : "fixtures",
    season: params.get("season"),
    fixture: params.get("fixture"),
    team: params.get("team"),
  };
}

function queryToSearch(query: AppQuery): string {
  const params = new URLSearchParams();
  if (query.view !== "fixtures") params.set("view", query.view);
  if (query.season) params.set("season", query.season);
  if (query.fixture) params.set("fixture", query.fixture);
  if (query.team) params.set("team", query.team);
  const s = params.toString();
  return s ? `?${s}` : "";
}

export interface SetQueryOptions {
  /** Use history.replaceState instead of pushState — for high-frequency updates
   * (e.g. each keystroke in a search box) that should not each create a Back-stop. */
  replace?: boolean;
}

/**
 * The entire app's navigable state lives in the URL's query string (never a path
 * segment, so this works correctly when served as a plain static file with no
 * server-side rewrite rule). Every state change updates history exactly once, as a
 * plain side effect of calling `setQuery` from an event handler — never from inside
 * a React state updater function, which React is free to invoke more than once (for
 * retried/discarded renders) and which must therefore stay pure. A `queryRef` tracks
 * the latest committed value synchronously so multiple `setQuery` calls in the same
 * tick (or calls that race a pending render) always merge onto the true latest state,
 * not a stale snapshot.
 */
export function useQueryState(): [AppQuery, (next: Partial<AppQuery>, options?: SetQueryOptions) => void] {
  const [query, setQueryState] = useState<AppQuery>(() =>
    typeof window === "undefined" ? DEFAULT_QUERY : parseQuery(window.location.search),
  );
  const queryRef = useRef(query);
  queryRef.current = query;

  useEffect(() => {
    const onPopState = () => {
      const next = parseQuery(window.location.search);
      queryRef.current = next;
      setQueryState(next);
    };
    window.addEventListener("popstate", onPopState);
    return () => window.removeEventListener("popstate", onPopState);
  }, []);

  const setQuery = useCallback((next: Partial<AppQuery>, options?: SetQueryOptions) => {
    const merged: AppQuery = { ...queryRef.current, ...next };
    const search = queryToSearch(merged);
    const url = `${window.location.pathname}${search}${window.location.hash}`;
    if (options?.replace) {
      window.history.replaceState(null, "", url);
    } else {
      window.history.pushState(null, "", url);
    }
    queryRef.current = merged;
    setQueryState(merged);
  }, []);

  return [query, setQuery];
}

import { useCallback, useEffect, useState } from "react";

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

/**
 * The entire app's navigable state lives in the URL's query string (never a path
 * segment, so this works correctly when served as a plain static file with no
 * server-side rewrite rule). Every state change does a `pushState` so the browser's
 * own Back/Forward buttons move through fixture/season/view history exactly as a
 * visitor expects from a normal multi-page site.
 */
export function useQueryState(): [AppQuery, (next: Partial<AppQuery>) => void] {
  const [query, setQueryState] = useState<AppQuery>(() =>
    typeof window === "undefined" ? DEFAULT_QUERY : parseQuery(window.location.search),
  );

  useEffect(() => {
    const onPopState = () => setQueryState(parseQuery(window.location.search));
    window.addEventListener("popstate", onPopState);
    return () => window.removeEventListener("popstate", onPopState);
  }, []);

  const setQuery = useCallback((next: Partial<AppQuery>) => {
    setQueryState((prev) => {
      const merged = { ...prev, ...next };
      const search = queryToSearch(merged);
      const url = `${window.location.pathname}${search}${window.location.hash}`;
      window.history.pushState(null, "", url);
      return merged;
    });
  }, []);

  return [query, setQuery];
}

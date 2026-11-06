import { useEffect, useState } from "react";
import type { ReplayDataset } from "../types";
import { validateReplayDataset } from "./validateReplayDataset";

export type ReplayDataState =
  | { status: "loading" }
  | { status: "error"; message: string }
  | { status: "ready"; data: ReplayDataset };

const DATA_URL = `${import.meta.env.BASE_URL}data/replays.json`;

export function useReplayData(): ReplayDataState {
  const [state, setState] = useState<ReplayDataState>({ status: "loading" });

  useEffect(() => {
    let cancelled = false;
    fetch(DATA_URL)
      .then((res) => {
        if (!res.ok) {
          throw new Error(`could not load historical fixture data (HTTP ${res.status})`);
        }
        return res.json();
      })
      .then((raw) => {
        if (cancelled) return;
        // The browser is its own trust boundary: the fetched JSON is independently,
        // strictly re-validated here — never assumed safe merely because it came
        // from this project's own generator. See validateReplayDataset's docstring.
        const result = validateReplayDataset(raw);
        if (!result.ok) {
          throw new Error(`historical fixture data failed validation: ${result.error}`);
        }
        setState({ status: "ready", data: result.data });
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        const message = err instanceof Error ? err.message : "unknown error loading fixture data";
        setState({ status: "error", message });
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return state;
}

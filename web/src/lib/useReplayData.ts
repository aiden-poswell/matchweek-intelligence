import { useEffect, useState } from "react";
import type { ReplayDataset } from "../types";

export type ReplayDataState =
  | { status: "loading" }
  | { status: "error"; message: string }
  | { status: "ready"; data: ReplayDataset };

const DATA_URL = `${import.meta.env.BASE_URL}data/replays.json`;

function validateDataset(raw: unknown): ReplayDataset {
  if (typeof raw !== "object" || raw === null) {
    throw new Error("replay data is not a JSON object");
  }
  const d = raw as Partial<ReplayDataset>;
  if (!Array.isArray(d.fixtures) || d.fixtures.length === 0) {
    throw new Error("replay data contains no fixtures");
  }
  if (typeof d.fixture_count !== "number" || d.fixtures.length !== d.fixture_count) {
    throw new Error("replay data fixture count does not match the fixture list");
  }
  if (!d.season_scorecards || !d.evaluation_seasons) {
    throw new Error("replay data is missing season scorecards");
  }
  return d as ReplayDataset;
}

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
        const data = validateDataset(raw);
        setState({ status: "ready", data });
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

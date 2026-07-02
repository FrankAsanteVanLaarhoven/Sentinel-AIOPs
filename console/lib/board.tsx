"use client";
// Shared client-side board state: environment, time range, the focused service
// (click-to-filter from topology/donut), and the live/paused toggle. Kept tiny
// and prop-free so any panel can read/write it.
import {
  createContext,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import type { Env, TimeRange } from "./types";

interface BoardState {
  env: Env;
  setEnv: (e: Env) => void;
  range: TimeRange;
  setRange: (r: TimeRange) => void;
  focus: string | null;
  setFocus: (s: string | null) => void;
  scenario: string;
  setScenario: (s: string) => void;
  live: boolean;
  setLive: (v: boolean) => void;
  demo: boolean;
}

const BoardContext = createContext<BoardState | null>(null);

export function BoardProvider({ children }: { children: ReactNode }) {
  const [env, setEnv] = useState<Env>("prod");
  const [range, setRange] = useState<TimeRange>("1h");
  const [focus, setFocus] = useState<string | null>(null);
  const [scenario, setScenarioState] = useState<string>("flag_spike");
  // Switching scenarios changes the root service, so drop any stale focus.
  const setScenario = (s: string) => {
    setScenarioState(s);
    setFocus(null);
  };
  const [live, setLive] = useState<boolean>(true);
  // Honour ?live=0 and ?scenario=<id> after mount (not in the initial state) so
  // server and client render identically — no hydration mismatch. Also makes
  // deep links to a specific scenario shareable.
  useEffect(() => {
    const q = new URLSearchParams(window.location.search);
    if (q.get("live") === "0") setLive(false);
    const s = q.get("scenario");
    if (s) setScenarioState(s);
  }, []);
  // Mirrors the engine's DATA_SOURCE; the badge is confirmed against /health too.
  const demo =
    (process.env.NEXT_PUBLIC_DATA_SOURCE ?? "demo").toLowerCase() !== "prom";

  const value = useMemo(
    () => ({
      env, setEnv, range, setRange, focus, setFocus,
      scenario, setScenario, live, setLive, demo,
    }),
    [env, range, focus, scenario, live, demo],
  );
  return <BoardContext.Provider value={value}>{children}</BoardContext.Provider>;
}

export function useBoard(): BoardState {
  const ctx = useContext(BoardContext);
  if (!ctx) throw new Error("useBoard must be used within BoardProvider");
  return ctx;
}

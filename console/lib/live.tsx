"use client";
// Single shared SSE connection to /api/stream. Opens only while the board is
// "live"; exposes the latest frame + connection state to any panel.
import {
  createContext,
  useContext,
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { useBoard } from "./board";
import type { Frame } from "./types";

interface LiveState {
  frame: Frame | null;
  connected: boolean;
}

const LiveContext = createContext<LiveState>({ frame: null, connected: false });

export function LiveProvider({ children }: { children: ReactNode }) {
  const { live, scenario } = useBoard();
  const [frame, setFrame] = useState<Frame | null>(null);
  const [connected, setConnected] = useState(false);
  const esRef = useRef<EventSource | null>(null);

  useEffect(() => {
    if (!live) {
      esRef.current?.close();
      esRef.current = null;
      setConnected(false);
      return;
    }
    const es = new EventSource(`/api/stream?scenario=${encodeURIComponent(scenario)}`);
    esRef.current = es;
    es.addEventListener("frame", (e) => {
      try {
        setFrame(JSON.parse((e as MessageEvent).data));
        setConnected(true);
      } catch {
        /* ignore malformed frame */
      }
    });
    es.addEventListener("engine_error", () => setConnected(false));
    es.onerror = () => setConnected(false);
    return () => {
      es.close();
      esRef.current = null;
      setConnected(false);
    };
  }, [live, scenario]);

  return (
    <LiveContext.Provider value={{ frame, connected }}>
      {children}
    </LiveContext.Provider>
  );
}

export function useLive(): LiveState {
  return useContext(LiveContext);
}

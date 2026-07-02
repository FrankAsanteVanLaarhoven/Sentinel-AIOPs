"use client";
import { useQuery } from "@tanstack/react-query";
import { useBoard } from "./board";
import type { Panels } from "./types";

// Shared query — all five P5 panels read from one fetch (TanStack dedupes).
export function usePanels() {
  const { scenario } = useBoard();
  return useQuery({
    queryKey: ["panels", scenario],
    queryFn: async (): Promise<Panels> => {
      const res = await fetch(`/api/panels?scenario=${encodeURIComponent(scenario)}`);
      if (!res.ok) throw new Error(`panels ${res.status}`);
      return res.json();
    },
  });
}

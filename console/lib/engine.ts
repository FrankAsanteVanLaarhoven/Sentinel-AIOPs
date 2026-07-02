// Typed, server-side client for the Sentinel FastAPI engine.
// Only called from route handlers (BFF) — never from the browser, so the engine
// URL stays server-side and no keys reach the client.
import "server-only";
import type {
  Incident,
  Topology,
  Changes,
  Telemetry,
  Frame,
  Panels,
  ScenarioMeta,
  Validation,
} from "./types";

const enc = encodeURIComponent;

const BASE = process.env.SENTINEL_ENGINE_URL ?? "http://127.0.0.1:8008";

export class EngineError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
    this.name = "EngineError";
  }
}

async function get<T>(path: string, revalidate = 0): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${BASE}${path}`, {
      // engine output is deterministic per source; keep it fresh but cheap
      next: { revalidate },
      headers: { accept: "application/json" },
    });
  } catch {
    throw new EngineError(`Sentinel engine unreachable at ${BASE}`, 503);
  }
  if (!res.ok) {
    throw new EngineError(`engine ${path} -> ${res.status}`, res.status);
  }
  return (await res.json()) as T;
}

export const engine = {
  base: BASE,
  health: () => get<{ status: string; dataSource: string; demo: boolean }>("/health"),
  scenarios: () =>
    get<{ scenarios: ScenarioMeta[]; active: string; demo: boolean }>("/scenarios"),
  investigate: (scenario = "flag_spike") =>
    get<Incident>(`/investigate?scenario=${enc(scenario)}`),
  topology: (scenario = "flag_spike") =>
    get<Topology>(`/topology?scenario=${enc(scenario)}`),
  changes: (scenario = "flag_spike") =>
    get<Changes>(`/changes?scenario=${enc(scenario)}`),
  telemetry: (range = "1h", service?: string, scenario = "flag_spike") =>
    get<Telemetry>(
      `/telemetry?range=${enc(range)}&scenario=${enc(scenario)}${
        service ? `&service=${enc(service)}` : ""
      }`,
    ),
  frame: (scenario = "flag_spike") => get<Frame>(`/frame?scenario=${enc(scenario)}`),
  panels: (scenario = "flag_spike") => get<Panels>(`/panels?scenario=${enc(scenario)}`),
  runbook: (scenario = "flag_spike") =>
    get<{ scenario: string; root?: string; markdown: string }>(
      `/runbook?scenario=${enc(scenario)}`,
    ),
  // Static across scenarios; cache for an hour.
  validation: () => get<Validation>("/validation", 3600),
};

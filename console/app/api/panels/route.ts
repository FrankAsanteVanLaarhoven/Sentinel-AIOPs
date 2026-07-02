import { NextRequest, NextResponse } from "next/server";
import { engine, EngineError } from "@/lib/engine";
import type { Panels } from "@/lib/types";

// GET /api/panels — derived secondary panels (host grid, trace, span
// throughput, latency heatmap, error share), computed by the engine in one pass.
export async function GET(req: NextRequest) {
  const scenario = new URL(req.url).searchParams.get("scenario") ?? "flag_spike";
  try {
    const data = await engine.panels(scenario);
    return NextResponse.json(data);
  } catch (e) {
    const status = e instanceof EngineError ? e.status : 500;
    return NextResponse.json(
      { error: e instanceof Error ? e.message : "panels failed" },
      { status },
    );
  }
}

export type { Panels };

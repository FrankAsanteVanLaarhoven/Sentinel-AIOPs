import { NextRequest, NextResponse } from "next/server";
import { engine, EngineError } from "@/lib/engine";

// GET /api/topology — services + dependency edges + per-service causal status.
export async function GET(req: NextRequest) {
  const scenario = new URL(req.url).searchParams.get("scenario") ?? "flag_spike";
  try {
    return NextResponse.json(await engine.topology(scenario));
  } catch (e) {
    const status = e instanceof EngineError ? e.status : 500;
    return NextResponse.json(
      { error: e instanceof Error ? e.message : "topology failed" },
      { status },
    );
  }
}

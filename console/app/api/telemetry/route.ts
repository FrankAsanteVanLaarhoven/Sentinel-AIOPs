import { NextRequest, NextResponse } from "next/server";
import { engine, EngineError } from "@/lib/engine";
import type { TimeRange } from "@/lib/types";

// GET /api/telemetry?range=1h&service=productcatalog
// Golden-signal series from the active DataProvider (engine is source of truth).
export async function GET(req: NextRequest) {
  const { searchParams } = new URL(req.url);
  const range = (searchParams.get("range") ?? "1h") as TimeRange;
  const service = searchParams.get("service") ?? undefined;
  const scenario = searchParams.get("scenario") ?? "flag_spike";
  try {
    const data = await engine.telemetry(range, service, scenario);
    return NextResponse.json(data);
  } catch (e) {
    const status = e instanceof EngineError ? e.status : 500;
    return NextResponse.json(
      { error: e instanceof Error ? e.message : "telemetry failed" },
      { status },
    );
  }
}

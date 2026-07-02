import { NextRequest, NextResponse } from "next/server";
import { engine, EngineError } from "@/lib/engine";

// GET /api/changes — changes ranked by the engine's score (service-match ×
// onset-proximity), each annotated with its naive recency rank so the UI can
// show the differentiator (true cause #1 vs what recency would have surfaced).
export async function GET(req: NextRequest) {
  const scenario = new URL(req.url).searchParams.get("scenario") ?? "flag_spike";
  try {
    return NextResponse.json(await engine.changes(scenario));
  } catch (e) {
    const status = e instanceof EngineError ? e.status : 500;
    return NextResponse.json(
      { error: e instanceof Error ? e.message : "changes failed" },
      { status },
    );
  }
}

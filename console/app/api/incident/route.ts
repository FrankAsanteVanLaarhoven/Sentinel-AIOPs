import { NextRequest, NextResponse } from "next/server";
import { engine, EngineError } from "@/lib/engine";

// GET /api/incident — the current investigation, proxied from the engine's
// /investigate. The Console renders this; it never derives the conclusion.
export async function GET(req: NextRequest) {
  const scenario = new URL(req.url).searchParams.get("scenario") ?? "flag_spike";
  try {
    return NextResponse.json(await engine.investigate(scenario));
  } catch (e) {
    const status = e instanceof EngineError ? e.status : 500;
    return NextResponse.json(
      { error: e instanceof Error ? e.message : "investigate failed" },
      { status },
    );
  }
}

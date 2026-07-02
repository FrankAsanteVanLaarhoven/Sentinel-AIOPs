import { NextResponse } from "next/server";
import { engine, EngineError } from "@/lib/engine";

// GET /api/scenarios — the demo scenario catalogue for the command-bar selector.
export async function GET() {
  try {
    return NextResponse.json(await engine.scenarios());
  } catch (e) {
    const status = e instanceof EngineError ? e.status : 500;
    return NextResponse.json(
      { error: e instanceof Error ? e.message : "scenarios failed", scenarios: [] },
      { status },
    );
  }
}

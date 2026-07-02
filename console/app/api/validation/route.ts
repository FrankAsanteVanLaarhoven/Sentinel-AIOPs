import { NextResponse } from "next/server";
import { engine, EngineError } from "@/lib/engine";

// GET /api/validation — the three-layer honesty story (learned detection envelope,
// deterministic localizer, measured real-incident baseline) in one payload.
export async function GET() {
  try {
    return NextResponse.json(await engine.validation());
  } catch (e) {
    const status = e instanceof EngineError ? e.status : 500;
    return NextResponse.json(
      { error: e instanceof Error ? e.message : "validation failed" },
      { status },
    );
  }
}

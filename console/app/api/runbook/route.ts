import { NextRequest, NextResponse } from "next/server";
import { engine, EngineError } from "@/lib/engine";

// GET /api/runbook?scenario= — the engine's Markdown incident runbook
// (method + confidence + failure modes + change ranking + human-gate note),
// for post-incident review and compliance export.
export async function GET(req: NextRequest) {
  const scenario = new URL(req.url).searchParams.get("scenario") ?? "flag_spike";
  try {
    return NextResponse.json(await engine.runbook(scenario));
  } catch (e) {
    const status = e instanceof EngineError ? e.status : 500;
    return NextResponse.json(
      { error: e instanceof Error ? e.message : "runbook failed", markdown: "" },
      { status },
    );
  }
}

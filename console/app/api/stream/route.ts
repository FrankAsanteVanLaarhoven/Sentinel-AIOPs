import { engine } from "@/lib/engine";

// GET /api/stream — Server-Sent Events; pushes one live metrics frame per second
// from the engine's /frame. Gives the board its "alive" feel. Demo frames jitter
// around the current incident state; a Prometheus source streams real values.
export const dynamic = "force-dynamic";
export const runtime = "nodejs";

export async function GET(req: Request) {
  const scenario = new URL(req.url).searchParams.get("scenario") ?? "flag_spike";
  const enc = new TextEncoder();
  let timer: ReturnType<typeof setInterval> | undefined;

  const stream = new ReadableStream({
    async start(controller) {
      const send = (event: string, data: unknown) => {
        try {
          controller.enqueue(enc.encode(`event: ${event}\ndata: ${JSON.stringify(data)}\n\n`));
        } catch {
          /* controller already closed */
        }
      };
      const tick = async () => {
        try {
          send("frame", await engine.frame(scenario));
        } catch {
          send("engine_error", { message: "engine unreachable" });
        }
      };
      await tick();
      timer = setInterval(tick, 1000);
    },
    cancel() {
      if (timer) clearInterval(timer);
    },
  });

  return new Response(stream, {
    headers: {
      "Content-Type": "text/event-stream; charset=utf-8",
      "Cache-Control": "no-cache, no-transform",
      Connection: "keep-alive",
      "X-Accel-Buffering": "no",
    },
  });
}

"use client";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useBoard } from "@/lib/board";
import type { Incident, InvestigationStep } from "@/lib/types";
import { Panel, PanelMessage } from "./Panel";
import { Badge, ConfidenceChip } from "./ui";

async function fetchIncident(scenario: string): Promise<Incident> {
  const res = await fetch(`/api/incident?scenario=${encodeURIComponent(scenario)}`);
  if (!res.ok) throw new Error(`incident ${res.status}`);
  return res.json();
}

const STEP_TONE: Record<InvestigationStep["key"], string> = {
  detected: "var(--warn)",
  localized: "var(--crit)",
  correlated: "var(--ice)",
  proposed: "var(--pearl)",
};

function BlastRadius({ items }: { items: { service: string; errorPct: number }[] }) {
  const max = Math.max(...items.map((i) => i.errorPct), 1);
  return (
    <div className="flex flex-col gap-1.5">
      {items.map((b, i) => (
        <div key={b.service} className="flex items-center gap-2">
          <span className="mono text-[10px] text-[var(--silver)] w-24 shrink-0 truncate">
            {b.service}
          </span>
          <div className="flex-1 h-1.5 rounded bg-white/5 overflow-hidden">
            <div
              className="h-full rounded"
              style={{
                width: `${(b.errorPct / max) * 100}%`,
                background: i === 0 ? "var(--crit)" : "var(--warn)",
              }}
            />
          </div>
          <span className="mono tnum text-[10px] text-[var(--mist)] w-9 text-right">
            {b.errorPct}%
          </span>
        </div>
      ))}
    </div>
  );
}

function Gate() {
  const [state, setState] = useState<"pending" | "approved" | "dismissed">("pending");
  if (state !== "pending") {
    const ok = state === "approved";
    return (
      <div
        className="mt-2 rounded-md border px-3 py-2 text-[11px] mono"
        style={{
          borderColor: ok
            ? "color-mix(in srgb, var(--ok) 45%, transparent)"
            : "var(--line-2)",
          color: ok ? "var(--ok)" : "var(--mist)",
          background: ok ? "color-mix(in srgb, var(--ok) 8%, transparent)" : "transparent",
        }}
        role="status"
      >
        {ok ? "✓ Rollback approved" : "Dismissed"} — logged for a human operator.
        <span className="text-[var(--dim)]">
          {" "}No action was executed; the engine only proposes.
        </span>
        <button
          onClick={() => setState("pending")}
          className="ml-2 underline text-[var(--dim)] hover:text-[var(--silver)]"
        >
          undo
        </button>
      </div>
    );
  }
  return (
    <div className="mt-2 flex items-center gap-2">
      <button
        onClick={() => setState("approved")}
        className="mono text-[11px] h-7 px-3 rounded-md font-medium transition-colors"
        style={{
          background: "color-mix(in srgb, var(--crit) 16%, transparent)",
          border: "1px solid color-mix(in srgb, var(--crit) 50%, transparent)",
          color: "var(--crit)",
        }}
      >
        Approve rollback
      </button>
      <button
        onClick={() => setState("dismissed")}
        className="mono text-[11px] h-7 px-3 rounded-md border border-[var(--line-2)] text-[var(--mist)] hover:text-[var(--silver)] transition-colors"
      >
        Dismiss
      </button>
      <span className="mono text-[9px] text-[var(--dim)] ml-auto">
        requires human approval
      </span>
    </div>
  );
}

function Timeline({ steps }: { steps: InvestigationStep[] }) {
  return (
    <ol className="flex flex-col">
      {steps.map((s, i) => {
        const tone = STEP_TONE[s.key];
        const last = i === steps.length - 1;
        return (
          <li key={s.key} className="flex gap-3">
            {/* rail */}
            <div className="flex flex-col items-center pt-1">
              <span
                className="dot"
                style={{ background: tone, boxShadow: `0 0 8px ${tone}66` }}
              />
              {!last && <span className="w-px flex-1 my-1 bg-[var(--line-2)]" />}
            </div>
            {/* body */}
            <div className={last ? "pb-1 flex-1" : "pb-4 flex-1"}>
              <div className="flex items-center justify-between gap-2">
                <span className="text-[12px] text-[var(--pearl)]" style={{ fontFamily: "var(--disp)" }}>
                  {s.title}
                </span>
                <span className="mono text-[10px] text-[var(--mist)] shrink-0">
                  {s.metric ?? (s.t != null ? `t=${s.t}m` : "")}
                </span>
              </div>
              <p className="mono text-[11px] leading-relaxed text-[var(--silver)] mt-1">
                {s.detail}
              </p>
              {s.key === "proposed" && s.gated && <Gate />}
            </div>
          </li>
        );
      })}
    </ol>
  );
}

export function InvestigationPanel() {
  const { scenario } = useBoard();
  const { data, isLoading, isError } = useQuery({
    queryKey: ["incident", scenario],
    queryFn: () => fetchIncident(scenario),
  });

  const right = data?.detected ? (
    <span className="flex items-center gap-1.5">
      {data.demo && <Badge tone="demo">demo</Badge>}
      <Badge tone="crit">SLO breach</Badge>
    </span>
  ) : (
    "human-gated"
  );

  return (
    <Panel
      title="Investigation"
      right={right}
      className="min-h-[520px] lg:sticky lg:top-[68px]"
      bodyClassName="flex flex-col gap-3 overflow-y-auto"
    >
      {isLoading && <PanelMessage kind="loading" title="Investigating…" />}
      {isError && (
        <PanelMessage kind="error" detail="Could not reach the Sentinel engine for the investigation." />
      )}
      {data && !data.detected && (
        <PanelMessage kind="empty" title="No SLO breach detected" detail="The engine found no burn in the window." />
      )}
      {data && data.detected && (
        <>
          {/* summary */}
          <div className="rounded-md border border-[var(--line)] bg-[var(--panel-2)] px-3 py-2">
            <div className="flex items-center justify-between">
              <span className="mono text-[11px] text-[var(--mist)]">root service</span>
              <span className="mono text-[10px] text-[var(--mist)]">
                MTTD <span className="text-[var(--ok)]">{data.mttd}m</span>
              </span>
            </div>
            <div className="flex items-center gap-2 mt-0.5">
              <span className="dot dot-crit" />
              <span className="text-[15px] text-[var(--pearl)]" style={{ fontFamily: "var(--disp)" }}>
                {data.root}
              </span>
              {data.localizationCorrect && (
                <Badge tone="ok" title="Matches the known injected root cause">verified</Badge>
              )}
            </div>
            {data.evidence && (
              <div className="mono text-[10px] text-[var(--dim)] mt-1.5">
                p95 {data.evidence.p95Before}ms → <span className="text-[var(--crit)]">{data.evidence.p95After}ms</span>
                {data.evidence.failingSpan && <> · span <span className="text-[var(--silver)]">{data.evidence.failingSpan}</span></>}
              </div>
            )}
          </div>

          {/* blast radius */}
          {data.blastRadius && data.blastRadius.length > 0 && (
            <div>
              <div className="mono text-[10px] uppercase tracking-[0.1em] text-[var(--mist)] mb-1.5">
                blast radius
              </div>
              <BlastRadius items={data.blastRadius} />
            </div>
          )}

          {/* stepped timeline + gate */}
          {data.steps && <Timeline steps={data.steps} />}

          {/* method + failure modes + confidence */}
          <div className="mt-auto pt-2 border-t border-[var(--line)] flex flex-col gap-2">
            <p className="mono text-[10px] leading-relaxed text-[var(--mist)]">
              <span className="text-[var(--silver)]">Method.</span> {data.method}
            </p>
            <details className="group">
              <summary className="mono text-[10px] text-[var(--dim)] hover:text-[var(--mist)] list-none flex items-center gap-1 select-none">
                <span className="group-open:rotate-90 transition-transform inline-block">▸</span>
                when this can be wrong ({data.failureModes.length})
              </summary>
              <ul className="mt-1.5 flex flex-col gap-1 pl-3">
                {data.failureModes.map((f, i) => (
                  <li key={i} className="mono text-[10px] leading-relaxed text-[var(--mist)] list-disc list-outside">
                    {f}
                  </li>
                ))}
              </ul>
            </details>
            {data.confidence != null && (
              <div className="flex items-center justify-between">
                <ConfidenceChip value={data.confidence} />
                <span className="mono text-[9px] text-[var(--dim)]">assistive · proposes only</span>
              </div>
            )}
          </div>
        </>
      )}
    </Panel>
  );
}

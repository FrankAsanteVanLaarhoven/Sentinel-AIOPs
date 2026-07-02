"use client";
import { useQuery } from "@tanstack/react-query";
import { useBoard } from "@/lib/board";
import type { Changes, ChangeItem } from "@/lib/types";
import { Panel, PanelMessage } from "./Panel";
import { Badge } from "./ui";

async function fetchChanges(scenario: string): Promise<Changes> {
  const res = await fetch(`/api/changes?scenario=${encodeURIComponent(scenario)}`);
  if (!res.ok) throw new Error(`changes ${res.status}`);
  return res.json();
}

function Row({ c, rank, max }: { c: ChangeItem; rank: number; max: number }) {
  const root = c.isRoot;
  // A change whose recency rank is better (lower) than its engine rank is what a
  // naive "most-recent-change" heuristic would have wrongly surfaced first.
  const recencyMisleads = c.recencyRank < rank + 1 && !root;
  return (
    <li className="rounded-md border border-[var(--line)] bg-[var(--panel-2)] px-3 py-2">
      <div className="flex items-center justify-between mono text-[11px]">
        <span className="flex items-center gap-1.5" style={{ color: root ? "var(--crit)" : "var(--silver)" }}>
          <span className="tnum">#{rank + 1}</span>
          <span>·</span>
          <span>{c.service}</span>
          {root && <Badge tone="crit">root cause</Badge>}
        </span>
        <span
          className="mono text-[10px] tnum"
          style={{ color: recencyMisleads ? "var(--warn)" : "var(--mist)" }}
          title={
            recencyMisleads
              ? "Naive recency ranks this change higher than it deserves."
              : "Where a naive most-recent-first heuristic would place this change."
          }
        >
          recency #{c.recencyRank}
        </span>
      </div>
      <div className="text-[12px] text-[var(--pearl)] mt-0.5">{c.change}</div>
      <div className="flex items-center gap-2 mt-2">
        <div className="h-1 flex-1 rounded bg-white/5 overflow-hidden">
          <div
            className="h-1 rounded"
            style={{
              width: `${(c.score / max) * 100}%`,
              background: root ? "var(--crit)" : "var(--ice)",
            }}
          />
        </div>
        <span className="mono text-[9px] text-[var(--mist)] tnum w-10 text-right">
          {c.score.toFixed(3)}
        </span>
      </div>
      <div className="mono text-[9px] text-[var(--dim)] mt-1">
        t={c.t}m · match {c.serviceMatch.toFixed(1)} × proximity {c.onsetProximity.toFixed(2)}
      </div>
    </li>
  );
}

export function ChangeRanking() {
  const { scenario } = useBoard();
  const { data, isLoading, isError } = useQuery({
    queryKey: ["changes", scenario],
    queryFn: () => fetchChanges(scenario),
  });

  const items = data?.items ?? [];
  const max = Math.max(...items.map((i) => i.score), 1e-6);
  // Which change would a naive "latest change is the suspect" view surface?
  const recencyPick = items.find((i) => i.recencyRank === 1);
  const enginePick = items[0];
  const differentiates =
    recencyPick && enginePick && recencyPick.service !== enginePick.service;

  return (
    <Panel title="Change correlation" right="score · recency" className="area-cr min-h-[200px]">
      {isLoading && <PanelMessage kind="loading" />}
      {isError && <PanelMessage kind="error" detail="Could not reach the Sentinel engine." />}
      {data && (
        <div className="flex flex-col gap-2">
          <ul className="flex flex-col gap-2">
            {items.map((c, i) => (
              <Row key={`${c.service}-${c.t}`} c={c} rank={i} max={max} />
            ))}
          </ul>
          {differentiates && (
            <p className="mono text-[10px] leading-relaxed text-[var(--mist)] border-t border-[var(--line)] pt-2">
              <span className="text-[var(--warn)]">Recency would mislead:</span> the
              most-recent change is{" "}
              <span className="text-[var(--silver)]">{recencyPick!.service}</span> (
              {recencyPick!.change.toLowerCase()}), which isn&apos;t erroring. The
              engine ranks{" "}
              <span className="text-[var(--crit)]">{enginePick!.service}</span> #1 by
              service-match × onset-proximity.
            </p>
          )}
        </div>
      )}
    </Panel>
  );
}

"use client";
import { useBoard } from "@/lib/board";
import { usePanels } from "@/lib/usePanels";
import type { HostGroup } from "@/lib/types";
import { Panel, PanelMessage } from "./Panel";

const cellColor = (c: string) =>
  c === "crit" ? "var(--crit)" : c === "warn" ? "var(--warn)" : "var(--ok)";

function Group({ h, dim, onClick }: { h: HostGroup; dim: boolean; onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      className="text-left rounded-md border border-[var(--line)] bg-[var(--panel-2)] px-2.5 py-2 flex flex-col gap-1.5 transition-opacity"
      style={{ opacity: dim ? 0.4 : 1 }}
    >
      <div className="flex items-center justify-between">
        <span className="mono text-[10px] text-[var(--silver)] truncate">{h.service}</span>
        <span className="mono text-[9px] text-[var(--mist)]">{h.total} pods</span>
      </div>
      <div className="flex flex-wrap gap-1">
        {h.cells.map((c, i) => (
          <span
            key={i}
            className="rounded-[2px]"
            style={{ width: 11, height: 11, background: cellColor(c), opacity: c === "ok" ? 0.55 : 1 }}
            title={`${h.service} pod ${i + 1}: ${c === "ok" ? "healthy" : c}`}
          />
        ))}
      </div>
      <div className="mono text-[9px] flex items-center gap-2">
        <span className="text-[var(--ok)]">{h.healthy} ok</span>
        {h.warn > 0 && <span className="text-[var(--warn)]">{h.warn} warn</span>}
        {h.crit > 0 && <span className="text-[var(--crit)]">{h.crit} crit</span>}
      </div>
    </button>
  );
}

export function HostHeatmap() {
  const { focus, setFocus } = useBoard();
  const { data, isLoading, isError } = usePanels();

  return (
    <Panel title="Host / pod health" right="cluster · use1-prod" className="area-hh min-h-[180px]" gridBg>
      {isLoading && <PanelMessage kind="loading" />}
      {isError && <PanelMessage kind="error" detail="Could not reach the Sentinel engine." />}
      {data && (
        <div className="grid gap-2 [grid-template-columns:repeat(auto-fill,minmax(150px,1fr))]">
          {data.hosts.map((h) => (
            <Group
              key={h.service}
              h={h}
              dim={!!focus && focus !== h.service}
              onClick={() => setFocus(focus === h.service ? null : h.service)}
            />
          ))}
        </div>
      )}
    </Panel>
  );
}

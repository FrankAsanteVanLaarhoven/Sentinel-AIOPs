"use client";
import "@xyflow/react/dist/style.css";
import { useMemo } from "react";
import {
  ReactFlow,
  Background,
  Handle,
  Position,
  type Node,
  type Edge,
  type NodeProps,
} from "@xyflow/react";
import { useQuery } from "@tanstack/react-query";
import { useBoard } from "@/lib/board";
import type { Topology, TopoService, Status } from "@/lib/types";
import { Panel, PanelMessage } from "./Panel";

const STATUS: Record<Status, string> = {
  ok: "var(--ok)",
  warn: "var(--warn)",
  root: "var(--crit)",
};

type SvcData = {
  label: string;
  status: Status;
  rps: number;
  errorPct: number;
  focused: boolean;
  hovered: boolean;
  dim: boolean;
};

function SvcNode({ data }: NodeProps) {
  const d = data as SvcData;
  const color = STATUS[d.status];
  const ring = d.focused
    ? `0 0 0 2px var(--ice)`
    : d.hovered
      ? `0 0 0 2px var(--ice)`
      : d.status === "root"
        ? `0 0 0 4px rgba(255,106,77,.18)`
        : "none";
  return (
    <div
      className="rounded-lg border bg-[var(--panel-2)] px-3 py-2 text-center select-none transition-opacity duration-150"
      style={{
        borderColor: color,
        borderWidth: 1.5,
        minWidth: 112,
        opacity: d.dim ? 0.4 : 1,
        boxShadow: ring,
        animation: d.status === "root" ? "pulse-ring 2.2s infinite" : undefined,
      }}
    >
      <Handle type="target" position={Position.Top} style={{ opacity: 0, pointerEvents: "none" }} />
      <div className="mono text-[11px] text-[var(--pearl)] flex items-center justify-center gap-1.5">
        <span className="dot" style={{ background: color }} />
        {d.label}
      </div>
      <div className="mono text-[9px] text-[var(--mist)] mt-1 flex items-center justify-center gap-2">
        <span style={{ color: d.errorPct >= 1 ? color : "var(--mist)" }}>
          {d.errorPct.toFixed(1)}%
        </span>
        <span className="text-[var(--dim)]">{d.rps}/s</span>
      </div>
      <Handle type="source" position={Position.Bottom} style={{ opacity: 0, pointerEvents: "none" }} />
    </div>
  );
}

const nodeTypes = { svc: SvcNode };

// Layered layout: a service's depth is the longest dependency chain beneath it.
// depth 0 = depends on nothing (a potential root) -> placed at the BOTTOM, so
// errors visibly propagate upward into it.
function layout(services: TopoService[]) {
  const byId = new Map(services.map((s) => [s.id, s]));
  const depthCache = new Map<string, number>();
  const depth = (id: string, seen = new Set<string>()): number => {
    if (depthCache.has(id)) return depthCache.get(id)!;
    if (seen.has(id)) return 0;
    seen.add(id);
    const deps = byId.get(id)?.dependsOn ?? [];
    const d = deps.length === 0 ? 0 : 1 + Math.max(...deps.map((x) => depth(x, seen)));
    depthCache.set(id, d);
    return d;
  };
  const maxDepth = Math.max(...services.map((s) => depth(s.id)), 0);
  const layers = new Map<number, string[]>();
  services.forEach((s) => {
    const d = depth(s.id);
    layers.set(d, [...(layers.get(d) ?? []), s.id]);
  });
  const pos = new Map<string, { x: number; y: number }>();
  const COL = 172;
  const ROW = 128;
  layers.forEach((ids, d) => {
    const y = (maxDepth - d) * ROW + 8;
    const w = (ids.length - 1) * COL;
    ids.forEach((id, i) => pos.set(id, { x: i * COL - w / 2 + 220, y }));
  });
  return pos;
}

async function fetchTopology(scenario: string): Promise<Topology> {
  const res = await fetch(`/api/topology?scenario=${encodeURIComponent(scenario)}`);
  if (!res.ok) throw new Error(`topology ${res.status}`);
  return res.json();
}

export function TopologyGraph() {
  const { focus, setFocus, hovered, setHovered, scenario } = useBoard();
  const { data, isLoading, isError } = useQuery({
    queryKey: ["topology", scenario],
    queryFn: () => fetchTopology(scenario),
  });

  const { nodes, edges } = useMemo(() => {
    if (!data) return { nodes: [] as Node[], edges: [] as Edge[] };
    const pos = layout(data.services);
    const nodes: Node[] = data.services.map((s) => ({
      id: s.id,
      type: "svc",
      position: pos.get(s.id) ?? { x: 0, y: 0 },
      data: {
        label: s.id,
        status: s.status,
        rps: s.rps,
        errorPct: s.errorPct,
        focused: focus === s.id,
        hovered: hovered === s.id,
        dim: !!hovered && hovered !== s.id && focus !== s.id,
      } satisfies SvcData,
      draggable: false,
    }));
    const edges: Edge[] = data.edges.map((e, i) => {
      const active = hovered === e.source || hovered === e.target;
      return {
        id: `e${i}`,
        source: e.source,
        target: e.target,
        animated: e.erroring,
        style: {
          stroke: e.erroring ? "var(--crit)" : "rgba(255,255,255,.16)",
          strokeWidth: e.erroring ? (active ? 2.6 : 1.8) : active ? 1.6 : 1,
          opacity: hovered && !active ? 0.25 : 1,
        },
      };
    });
    return { nodes, edges };
  }, [data, focus, hovered]);

  return (
    <Panel
      title="Service topology"
      right={data?.root ? `root · ${data.root}` : "causal"}
      className="area-topo min-h-[360px]"
    >
      {isLoading && <PanelMessage kind="loading" title="Awaiting topology" />}
      {isError && <PanelMessage kind="error" detail="Could not reach the Sentinel engine." />}
      {data && (
        <div className="relative h-full w-full min-h-[320px]">
          <ReactFlow
            nodes={nodes}
            edges={edges}
            nodeTypes={nodeTypes}
            fitView
            fitViewOptions={{ padding: 0.18 }}
            proOptions={{ hideAttribution: true }}
            nodesDraggable={false}
            nodesConnectable={false}
            elementsSelectable
            zoomOnScroll={false}
            panOnScroll
            onNodeClick={(_, n) => setFocus(focus === n.id ? null : n.id)}
            onPaneClick={() => setFocus(null)}
            onNodeMouseEnter={(_, n) => setHovered(n.id)}
            onNodeMouseLeave={() => setHovered(null)}
          >
            <Background color="rgba(255,255,255,.05)" gap={18} />
          </ReactFlow>
          {/* legend */}
          <div className="absolute left-2 bottom-2 mono text-[9px] text-[var(--mist)] flex items-center gap-3 rounded-md border border-[var(--line)] bg-[color:color-mix(in_srgb,var(--panel)_80%,transparent)] px-2 py-1 backdrop-blur-sm">
            <span className="flex items-center gap-1"><span className="dot dot-crit" />root cause</span>
            <span className="flex items-center gap-1"><span className="dot dot-warn" />symptom</span>
            <span className="flex items-center gap-1"><span className="dot dot-ok" />healthy</span>
          </div>
          <div className="absolute right-2 top-2 mono text-[9px] text-[var(--dim)]">
            click a node to focus the board
          </div>
        </div>
      )}
    </Panel>
  );
}

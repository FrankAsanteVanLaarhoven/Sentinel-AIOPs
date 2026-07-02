"use client";
import { usePanels } from "@/lib/usePanels";
import { Panel, PanelMessage } from "./Panel";
import { C } from "./charts/echartsTheme";

export function TraceWaterfall() {
  const { data, isLoading, isError } = usePanels();

  const trace = data?.trace;
  const W = 1000;
  const labelW = 296;
  const trackX = labelW + 12;
  const trackW = W - trackX - 12;
  const rowH = 30;
  const top = 26;
  const spans = trace?.spans ?? [];
  const H = top + spans.length * rowH + 8;
  const total = trace?.total ?? 1;
  const ticks = [0, 0.25, 0.5, 0.75, 1];

  return (
    <Panel
      title="Trace waterfall"
      right={trace ? `trace ${trace.traceId} · ${trace.total}ms` : "failing trace"}
      className="area-tw min-h-[180px]"
    >
      {isLoading && <PanelMessage kind="loading" />}
      {isError && <PanelMessage kind="error" detail="Could not reach the Sentinel engine." />}
      {trace && (
        <svg viewBox={`0 0 ${W} ${H}`} width="100%" height={H} preserveAspectRatio="xMinYMin meet" className="max-w-full">
          {/* time axis */}
          {ticks.map((f) => (
            <g key={f}>
              <line
                x1={trackX + f * trackW}
                y1={top - 6}
                x2={trackX + f * trackW}
                y2={H - 6}
                stroke={C.faint}
                strokeWidth={1}
              />
              <text
                x={trackX + f * trackW}
                y={top - 10}
                fill={C.dim}
                fontFamily={C.mono}
                fontSize={10}
                textAnchor={f === 1 ? "end" : f === 0 ? "start" : "middle"}
              >
                {Math.round(f * total)}ms
              </text>
            </g>
          ))}

          {spans.map((s, i) => {
            const y = top + i * rowH;
            const isErr = s.status === "ERROR";
            const bx = trackX + (s.start / total) * trackW;
            const bw = Math.max(3, (s.dur / total) * trackW);
            const fill = isErr ? C.crit : C.ice;
            return (
              <g key={i}>
                <rect x={0} y={y} width={W} height={rowH} fill={i % 2 ? "rgba(255,255,255,.015)" : "transparent"} />
                {/* label, indented by depth */}
                <text
                  x={10 + s.depth * 16}
                  y={y + rowH / 2 + 3}
                  fill={isErr ? C.crit : C.pearl}
                  fontFamily={C.mono}
                  fontSize={11}
                >
                  {s.name}
                </text>
                {/* bar */}
                <rect x={bx} y={y + (rowH - 12) / 2} width={bw} height={12} rx={2} fill={fill} fillOpacity={isErr ? 0.9 : 0.65} />
                {isErr && (
                  <rect x={bx} y={y + (rowH - 12) / 2} width={bw} height={12} rx={2} fill="none" stroke={C.crit} strokeWidth={1} />
                )}
                {/* duration */}
                <text
                  x={bx + bw + 6}
                  y={y + rowH / 2 + 3}
                  fill={C.mist}
                  fontFamily={C.mono}
                  fontSize={10}
                >
                  {s.dur}ms{isErr ? " · ERROR" : ""}
                </text>
              </g>
            );
          })}
        </svg>
      )}
    </Panel>
  );
}

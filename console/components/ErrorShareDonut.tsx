"use client";
import { useMemo } from "react";
import ReactECharts from "echarts-for-react";
import type { EChartsOption } from "echarts";
import { useBoard } from "@/lib/board";
import { usePanels } from "@/lib/usePanels";
import { Panel, PanelMessage } from "./Panel";
import { C, tooltipBase } from "./charts/echartsTheme";

const statusColor = (s: string, dim = false) =>
  s === "root" ? C.crit : s === "warn" ? C.warn : dim ? C.dim : C.ok;

export function ErrorShareDonut() {
  const { focus, setFocus } = useBoard();
  const { data, isLoading, isError } = usePanels();

  const option = useMemo<EChartsOption | null>(() => {
    if (!data) return null;
    const rows = data.errorShare.filter((r) => r.value > 0);
    const total = rows.reduce((s, r) => s + r.value, 0);
    return {
      backgroundColor: "transparent",
      animation: false,
      tooltip: {
        ...tooltipBase,
        trigger: "item",
        formatter: (p: unknown) => {
          const d = p as { name: string; value: number; percent: number };
          return `<span style="color:${C.mist}">${d.name}</span><br/><b>${d.value}</b> err/s · ${d.percent}%`;
        },
      },
      series: [
        {
          type: "pie",
          radius: ["56%", "80%"],
          center: ["50%", "50%"],
          avoidLabelOverlap: true,
          padAngle: 2,
          itemStyle: { borderRadius: 3, borderColor: C.panel2, borderWidth: 1 },
          label: { show: false },
          labelLine: { show: false },
          data: rows.map((r) => ({
            name: r.service,
            value: r.value,
            itemStyle: {
              color: statusColor(r.status),
              opacity: focus && focus !== r.service ? 0.32 : 1,
            },
          })),
        },
      ],
      graphic: {
        type: "group",
        left: "center",
        top: "center",
        children: [
          {
            type: "text",
            style: {
              text: `${Math.round(total)}`,
              fill: C.pearl,
              font: `600 20px ${C.mono}`,
              textAlign: "center",
            },
            top: -12,
          },
          {
            type: "text",
            style: { text: "err/s total", fill: C.mist, font: `10px ${C.mono}`, textAlign: "center" },
            top: 12,
          },
        ],
      },
    };
  }, [data, focus]);

  return (
    <Panel title="Error share" right="by service" className="area-dn min-h-[200px]">
      {isLoading && <PanelMessage kind="loading" />}
      {isError && <PanelMessage kind="error" detail="Could not reach the Sentinel engine." />}
      {data && (
        <div className="h-full w-full min-h-[176px] flex flex-col">
          <div className="flex-1 min-h-[128px]">
            <ReactECharts
              option={option!}
              style={{ height: "100%", width: "100%", minHeight: 128 }}
              notMerge
              lazyUpdate
              opts={{ renderer: "canvas" }}
              onEvents={{
                click: (p: { name?: string }) =>
                  p.name && setFocus(focus === p.name ? null : p.name),
              }}
            />
          </div>
          <div className="flex flex-wrap gap-x-3 gap-y-1 justify-center pt-1">
            {data.errorShare
              .filter((r) => r.value > 0)
              .map((r) => (
                <button
                  key={r.service}
                  onClick={() => setFocus(focus === r.service ? null : r.service)}
                  className="mono text-[9px] flex items-center gap-1"
                  style={{ color: focus && focus !== r.service ? C.dim : C.mist }}
                >
                  <span className="dot" style={{ background: statusColor(r.status) }} />
                  {r.service}
                </button>
              ))}
          </div>
        </div>
      )}
    </Panel>
  );
}

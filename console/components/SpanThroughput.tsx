"use client";
import { useMemo } from "react";
import ReactECharts from "echarts-for-react";
import type { EChartsOption } from "echarts";
import { useBoard } from "@/lib/board";
import { usePanels } from "@/lib/usePanels";
import { Panel, PanelMessage } from "./Panel";
import { C, tooltipBase, axisLabel } from "./charts/echartsTheme";

const statusColor = (s: string) =>
  s === "root" ? C.crit : s === "warn" ? C.warn : C.ice;

export function SpanThroughput() {
  const { focus, setFocus } = useBoard();
  const { data, isLoading, isError } = usePanels();

  const option = useMemo<EChartsOption | null>(() => {
    if (!data) return null;
    const rows = [...data.spanThroughput].sort((a, b) => a.rps - b.rps);
    return {
      backgroundColor: "transparent",
      animation: false,
      grid: { left: 84, right: 34, top: 8, bottom: 6 },
      tooltip: {
        ...tooltipBase,
        trigger: "item",
        formatter: (p: unknown) => {
          const d = p as { name: string; value: number };
          return `<span style="color:${C.mist}">${d.name}</span> <b>${d.value}</b> spans/s`;
        },
      },
      xAxis: { type: "value", splitLine: { lineStyle: { color: C.faint } }, axisLabel },
      yAxis: {
        type: "category",
        data: rows.map((r) => r.service),
        axisLine: { lineStyle: { color: C.line } },
        axisTick: { show: false },
        axisLabel: { ...axisLabel, fontSize: 10 },
      },
      series: [
        {
          type: "bar",
          data: rows.map((r) => ({
            value: r.rps,
            itemStyle: {
              color: statusColor(r.status),
              opacity: focus && focus !== r.service ? 0.35 : 0.9,
              borderRadius: [0, 3, 3, 0],
            },
          })),
          barWidth: 12,
          label: {
            show: true,
            position: "right",
            formatter: "{c}",
            color: C.mist,
            fontFamily: C.mono,
            fontSize: 10,
          },
        },
      ],
    };
  }, [data, focus]);

  return (
    <Panel title="Span throughput" right="spans/s" className="area-sp min-h-[180px]" gridBg>
      {isLoading && <PanelMessage kind="loading" />}
      {isError && <PanelMessage kind="error" detail="Could not reach the Sentinel engine." />}
      {data && (
        <ReactECharts
          option={option!}
          style={{ height: "100%", width: "100%", minHeight: 152 }}
          notMerge
          lazyUpdate
          opts={{ renderer: "canvas" }}
          onEvents={{
            click: (p: { name?: string }) =>
              p.name && setFocus(focus === p.name ? null : p.name),
          }}
        />
      )}
    </Panel>
  );
}

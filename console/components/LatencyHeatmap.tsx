"use client";
import { useMemo } from "react";
import ReactECharts from "echarts-for-react";
import type { EChartsOption } from "echarts";
import { usePanels } from "@/lib/usePanels";
import { Panel, PanelMessage } from "./Panel";
import { C, tooltipBase, axisLabel, prefersReducedMotion } from "./charts/echartsTheme";

export function LatencyHeatmap() {
  const { data, isLoading, isError } = usePanels();

  const option = useMemo<EChartsOption | null>(() => {
    if (!data) return null;
    const lh = data.latencyHeatmap;
    const values = lh.cells.map((c) => c[2]);
    const maxV = Math.max(...values, 1);
    const minV = Math.min(...values, 0);
    // thin the x labels so they stay readable
    const xLabels = lh.t.map((v) => `${v}`);
    return {
      backgroundColor: "transparent",
      animation: !prefersReducedMotion(),
      grid: { left: 34, right: 12, top: 8, bottom: 30 },
      tooltip: {
        ...tooltipBase,
        position: "top",
        formatter: (p: unknown) => {
          const d = p as { data: [number, number, number] };
          return `<span style="color:${C.mist}">t=${d.data[0]}m · ${lh.bands[d.data[1]]}</span> <b>${d.data[2]}ms</b>`;
        },
      },
      xAxis: {
        type: "category",
        data: xLabels,
        axisLine: { lineStyle: { color: C.line } },
        axisTick: { show: false },
        axisLabel: { ...axisLabel, interval: 9, formatter: (v: string) => `${v}m` },
        splitArea: { show: false },
      },
      yAxis: {
        type: "category",
        data: lh.bands,
        axisLine: { lineStyle: { color: C.line } },
        axisTick: { show: false },
        axisLabel,
        splitArea: { show: false },
      },
      visualMap: {
        min: minV,
        max: maxV,
        calculable: false,
        show: false,
        inRange: {
          color: ["rgba(127,166,217,.12)", C.ice, C.warn, C.crit],
        },
      },
      series: [
        {
          type: "heatmap",
          data: lh.cells,
          itemStyle: { borderColor: C.panel2, borderWidth: 0.5 },
          emphasis: { itemStyle: { borderColor: C.pearl, borderWidth: 1 } },
          progressive: 0,
        },
      ],
    };
  }, [data]);

  return (
    <Panel
      title="Latency heatmap"
      right={data ? `${data.latencyHeatmap.service} · p50–p99` : "p50–p99"}
      className="area-lh min-h-[180px]"
    >
      {isLoading && <PanelMessage kind="loading" />}
      {isError && <PanelMessage kind="error" detail="Could not reach the Sentinel engine." />}
      {data && (
        <ReactECharts
          option={option!}
          style={{ height: "100%", width: "100%", minHeight: 152 }}
          notMerge
          lazyUpdate
          opts={{ renderer: "canvas" }}
        />
      )}
    </Panel>
  );
}

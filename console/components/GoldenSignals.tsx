"use client";
import { useMemo } from "react";
import ReactECharts from "echarts-for-react";
import type { EChartsOption } from "echarts";
import { useQuery } from "@tanstack/react-query";
import { useBoard } from "@/lib/board";
import type { Telemetry } from "@/lib/types";
import { Panel, PanelMessage } from "./Panel";
import { C, catAxis, valAxis, tooltipBase, prefersReducedMotion } from "./charts/echartsTheme";

async function fetchTelemetry(
  range: string,
  service: string | null,
  scenario: string,
): Promise<Telemetry> {
  const qs = new URLSearchParams({ range, scenario });
  if (service) qs.set("service", service);
  const res = await fetch(`/api/telemetry?${qs}`);
  if (!res.ok) throw new Error(`telemetry ${res.status}`);
  return res.json();
}

export function GoldenSignals() {
  const { range, focus, scenario } = useBoard();
  const { data, isLoading, isError } = useQuery({
    queryKey: ["telemetry", range, focus, scenario],
    queryFn: () => fetchTelemetry(range, focus, scenario),
  });

  const option = useMemo<EChartsOption | null>(() => {
    if (!data) return null;
    const { t, err, p95, rps, slo, incident, changes } = data;
    const incArea =
      incident != null
        ? [
            [
              { xAxis: t[incident[0]] },
              { xAxis: t[incident[1]] },
            ],
          ]
        : [];
    const changeLines = changes.map((c) => ({
      xAxis: t[c.t],
      lineStyle: {
        color: c.service === data.service ? C.crit : C.dim,
        type: "dashed" as const,
        width: 1,
      },
      label: {
        show: false,
      },
    }));

    return {
      backgroundColor: "transparent",
      animationDuration: prefersReducedMotion() ? 0 : 220,
      grid: [
        { left: 46, right: 14, top: 10, height: "34%" },
        { left: 46, right: 14, top: "52%", height: "17%" },
        { left: 46, right: 14, top: "75%", height: "17%" },
      ],
      axisPointer: { link: [{ xAxisIndex: "all" }], lineStyle: { color: C.line } },
      tooltip: {
        ...tooltipBase,
        trigger: "axis",
        axisPointer: { type: "line" },
        formatter: (params: unknown) => {
          const arr = params as { axisValue: string; seriesName: string; data: number; marker: string }[];
          if (!arr?.length) return "";
          const head = `<span style="color:${C.mist}">t=${arr[0].axisValue}m</span>`;
          const rows = arr
            .map(
              (p) =>
                `${p.marker}<span style="color:${C.pearl}">${p.seriesName}</span> <b>${p.data}</b>`,
            )
            .join("<br/>");
          return `${head}<br/>${rows}`;
        },
      },
      xAxis: [
        { ...catAxis(t, false), gridIndex: 0 },
        { ...catAxis(t, false), gridIndex: 1 },
        { ...catAxis(t, true), gridIndex: 2 },
      ],
      yAxis: [
        {
          ...valAxis({ axisLabel: { color: C.mist, fontFamily: C.mono, fontSize: 10, formatter: "{value}%" } }),
          gridIndex: 0,
          name: "error %",
          nameLocation: "end",
          nameGap: 4,
          nameTextStyle: { color: C.dim, fontFamily: C.mono, fontSize: 9, align: "left", verticalAlign: "bottom" },
        },
        {
          ...valAxis({ axisLabel: { color: C.mist, fontFamily: C.mono, fontSize: 10, formatter: "{value}" } }),
          gridIndex: 1,
          name: "p95 ms",
          nameLocation: "end",
          nameGap: 4,
          nameTextStyle: { color: C.dim, fontFamily: C.mono, fontSize: 9, align: "left", verticalAlign: "bottom" },
        },
        {
          ...valAxis({ axisLabel: { color: C.mist, fontFamily: C.mono, fontSize: 10 } }),
          gridIndex: 2,
          name: "rps",
          nameLocation: "end",
          nameGap: 4,
          nameTextStyle: { color: C.dim, fontFamily: C.mono, fontSize: 9, align: "left", verticalAlign: "bottom" },
        },
      ],
      series: [
        {
          name: "error ratio",
          type: "line",
          xAxisIndex: 0,
          yAxisIndex: 0,
          smooth: true,
          symbol: "none",
          data: err,
          lineStyle: { width: 2, color: C.crit },
          areaStyle: { color: "rgba(255,106,77,.10)" },
          markLine: {
            silent: true,
            symbol: "none",
            data: [
              {
                yAxis: slo,
                lineStyle: { color: C.warn, type: "dashed", width: 1 },
                label: {
                  formatter: `SLO ${slo}%`,
                  color: C.warn,
                  fontFamily: C.mono,
                  fontSize: 9,
                  position: "insideEndTop",
                },
              },
              ...changeLines,
            ],
          },
          markArea: {
            silent: true,
            itemStyle: { color: "rgba(255,106,77,.06)" },
            data: incArea as never,
          },
        },
        {
          name: "p95 latency",
          type: "line",
          xAxisIndex: 1,
          yAxisIndex: 1,
          smooth: true,
          symbol: "none",
          data: p95,
          lineStyle: { width: 1.5, color: C.ice },
          areaStyle: { color: "rgba(127,166,217,.08)" },
        },
        {
          name: "rps",
          type: "line",
          xAxisIndex: 2,
          yAxisIndex: 2,
          smooth: true,
          symbol: "none",
          data: rps,
          lineStyle: { width: 1.5, color: C.mist },
          areaStyle: { color: "rgba(121,131,154,.08)" },
        },
      ],
      dataZoom: [
        { type: "inside", xAxisIndex: [0, 1, 2], zoomOnMouseWheel: false },
        {
          type: "slider",
          xAxisIndex: [0, 1, 2],
          height: 12,
          bottom: 2,
          borderColor: "transparent",
          backgroundColor: "rgba(255,255,255,.02)",
          fillerColor: "rgba(127,166,217,.12)",
          handleStyle: { color: C.ice },
          moveHandleStyle: { color: C.ice },
          textStyle: { color: C.mist, fontFamily: C.mono, fontSize: 9 },
          labelFormatter: (v: number) => `${data.t[v] ?? v}m`,
        },
      ],
    };
  }, [data]);

  const right = data ? `${data.service} · ${data.range}` : "error · p95 · rps";

  return (
    <Panel title="Golden signals" right={right} className="area-gs min-h-[300px]" gridBg>
      {isLoading && <PanelMessage kind="loading" />}
      {isError && (
        <PanelMessage kind="error" detail="Could not reach the Sentinel engine for telemetry." />
      )}
      {option && (
        <ReactECharts
          option={option}
          style={{ height: "100%", width: "100%", minHeight: 236 }}
          notMerge
          lazyUpdate
          opts={{ renderer: "canvas" }}
        />
      )}
    </Panel>
  );
}

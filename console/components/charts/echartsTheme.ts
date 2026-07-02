// Shared velvet ECharts building blocks. Canvas renderer, mono numerals,
// hairline axes, restrained accents. Keep every chart visually one system.
import type { EChartsOption } from "echarts";

// Honour the OS "reduce motion" setting for canvas charts too (CSS only covers
// DOM animation). Safe on the server (returns false).
export const prefersReducedMotion = () =>
  typeof window !== "undefined" &&
  window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;

export const C = {
  panel2: "#10141d",
  line: "rgba(255,255,255,.13)",
  faint: "rgba(255,255,255,.06)",
  pearl: "#ebeef6",
  mist: "#79839a",
  dim: "#4c566b",
  ice: "#7fa6d9",
  ok: "#5fd08a",
  warn: "#e8b24c",
  crit: "#ff6a4d",
  mono: "IBM Plex Mono, ui-monospace, monospace",
};

export const axisLabel = {
  color: C.mist,
  fontFamily: C.mono,
  fontSize: 10,
};

export const tooltipBase = {
  backgroundColor: C.panel2,
  borderColor: C.line,
  borderWidth: 1,
  padding: [6, 10] as number[],
  textStyle: { color: C.pearl, fontFamily: C.mono, fontSize: 11 },
  extraCssText: "border-radius:8px;box-shadow:0 8px 30px rgba(0,0,0,.5);",
};

export function catAxis(data: string[], showLabel = true) {
  return {
    type: "category" as const,
    data,
    boundaryGap: false,
    axisTick: { show: false },
    axisLine: { lineStyle: { color: C.line } },
    axisLabel: showLabel
      ? { ...axisLabel, formatter: (v: string) => `${v}m` }
      : { show: false },
  };
}

// Only accepts an axisLabel override — never a `type`, so the value-axis
// literal doesn't get widened when spread into a chart option.
export function valAxis(over: { axisLabel?: object } = {}) {
  return {
    type: "value" as const,
    splitLine: { lineStyle: { color: C.faint } },
    axisLabel: over.axisLabel ?? axisLabel,
  };
}

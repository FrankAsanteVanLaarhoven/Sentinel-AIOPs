// Small, dependency-free formatters. Numbers render in tabular mono everywhere.

export const pct = (v: number, d = 1) => `${v.toFixed(d)}%`;
export const ms = (v: number) => `${Math.round(v)}ms`;
export const int = (v: number) => Math.round(v).toLocaleString("en-US");

export const rps = (v: number) => `${int(v)}/s`;

export function statusColor(status: "ok" | "warn" | "root" | "crit"): string {
  switch (status) {
    case "ok":
      return "var(--ok)";
    case "warn":
      return "var(--warn)";
    default:
      return "var(--crit)";
  }
}

export function statusDotClass(status: "ok" | "warn" | "root" | "crit"): string {
  return status === "ok" ? "dot-ok" : status === "warn" ? "dot-warn" : "dot-crit";
}

// SLO burn state for a metric vs its threshold -> drives StatCard colour.
export function burnState(value: number, threshold: number): "ok" | "warn" | "crit" {
  if (value >= threshold) return "crit";
  if (value >= threshold * 0.6) return "warn";
  return "ok";
}

export const clamp = (v: number, lo: number, hi: number) =>
  Math.max(lo, Math.min(hi, v));

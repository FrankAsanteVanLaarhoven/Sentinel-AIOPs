"use client";
import { useQuery } from "@tanstack/react-query";
import { useBoard } from "@/lib/board";
import { useLive } from "@/lib/live";
import type { Telemetry } from "@/lib/types";
import { StatusDot } from "./ui";
import { pct, ms, clamp } from "@/lib/format";

type Burn = "ok" | "warn" | "crit";
const color = (b: Burn) =>
  b === "ok" ? "var(--ok)" : b === "warn" ? "var(--warn)" : "var(--crit)";

function Sparkline({
  data,
  stroke,
  width = 132,
  height = 30,
}: {
  data: number[];
  stroke: string;
  width?: number;
  height?: number;
}) {
  if (data.length < 2) return <div style={{ height }} />;
  const min = Math.min(...data);
  const max = Math.max(...data);
  const span = max - min || 1;
  const step = width / (data.length - 1);
  const pts = data.map((v, i) => {
    const x = i * step;
    const y = height - ((v - min) / span) * (height - 4) - 2;
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  });
  const area = `0,${height} ${pts.join(" ")} ${width},${height}`;
  const id = `sg-${stroke.replace(/[^a-z]/gi, "")}`;
  return (
    <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`} className="w-full" preserveAspectRatio="none" aria-hidden>
      <defs>
        <linearGradient id={id} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={stroke} stopOpacity="0.22" />
          <stop offset="100%" stopColor={stroke} stopOpacity="0" />
        </linearGradient>
      </defs>
      <polygon points={area} fill={`url(#${id})`} />
      <polyline points={pts.join(" ")} fill="none" stroke={stroke} strokeWidth="1.5" strokeLinejoin="round" strokeLinecap="round" />
    </svg>
  );
}

function Card({
  area,
  label,
  value,
  unit,
  burn,
  spark,
  sub,
}: {
  area: string;
  label: string;
  value: string;
  unit?: string;
  burn: Burn;
  spark: number[];
  sub: string;
}) {
  return (
    <section
      className={`${area} rounded-lg border border-[var(--line)] bg-[var(--panel)] p-3 flex flex-col gap-1.5 min-h-[92px]`}
      style={{ boxShadow: `inset 3px 0 0 0 ${color(burn)}` }}
    >
      <div className="flex items-center justify-between">
        <span className="mono text-[10px] uppercase tracking-[0.1em] text-[var(--mist)]">{label}</span>
        <StatusDot status={burn} />
      </div>
      <div className="flex items-baseline gap-1">
        <span className="mono tnum text-[26px] leading-none" style={{ color: color(burn) }}>
          {value}
        </span>
        {unit && <span className="mono text-[11px] text-[var(--mist)]">{unit}</span>}
      </div>
      <div className="mt-auto -mx-1">
        <Sparkline data={spark} stroke={color(burn)} />
      </div>
      <span className="mono text-[10px] text-[var(--dim)] truncate">{sub}</span>
    </section>
  );
}

function CardSkeleton({ area, label }: { area: string; label: string }) {
  return (
    <section className={`${area} rounded-lg border border-[var(--line)] bg-[var(--panel)] p-3 flex flex-col gap-2 min-h-[92px]`}>
      <div className="mono text-[10px] uppercase tracking-[0.1em] text-[var(--mist)]">{label}</div>
      <div className="skeleton h-7 w-24" />
      <div className="skeleton h-5 w-full mt-auto" />
    </section>
  );
}

const LABELS = ["error rate", "p95 latency", "availability", "error budget"];

export function StatCards() {
  const { range, focus, scenario, live } = useBoard();
  const { frame } = useLive();
  const { data, isLoading, isError } = useQuery({
    queryKey: ["telemetry", range, focus, scenario],
    queryFn: async (): Promise<Telemetry> => {
      const qs = new URLSearchParams({ range, scenario });
      if (focus) qs.set("service", focus);
      const res = await fetch(`/api/telemetry?${qs}`);
      if (!res.ok) throw new Error(`telemetry ${res.status}`);
      return res.json();
    },
  });

  if (isLoading || isError || !data) {
    return (
      <>
        {["area-s1", "area-s2", "area-s3", "area-s4"].map((a, i) => (
          <CardSkeleton key={a} area={a} label={LABELS[i]} />
        ))}
      </>
    );
  }

  const { err, p95, slo, service } = data;
  // When streaming, overlay the current reading with the live frame so the
  // headline numbers tick each second; the sparkline stays the windowed series.
  const liveSvc = live ? frame?.services?.[service] : undefined;
  const errNow = liveSvc?.err ?? err.at(-1) ?? 0;
  const p95Now = liveSvc?.p95 ?? p95.at(-1) ?? 0;
  const avail = 100 - errNow;
  const availSpark = err.map((e) => 100 - e);
  const meanErr = err.reduce((s, v) => s + v, 0) / err.length;
  const burnX = meanErr / slo;
  const budgetRemaining = clamp((1 - burnX) * 100, 0, 100);

  const errBurn: Burn = errNow >= slo ? "crit" : errNow >= slo * 0.6 ? "warn" : "ok";
  const p95Burn: Burn = p95Now >= 250 ? "crit" : p95Now >= 180 ? "warn" : "ok";
  const availBurn: Burn = avail >= 99.9 ? "ok" : avail >= 99 ? "warn" : "crit";
  const budgetBurn: Burn = budgetRemaining > 30 ? "ok" : budgetRemaining > 0 ? "warn" : "crit";

  return (
    <>
      <Card area="area-s1" label="error rate" value={pct(errNow, 1)} burn={errBurn} spark={err} sub={`${service} · SLO ${slo}%`} />
      <Card area="area-s2" label="p95 latency" value={ms(p95Now)} burn={p95Burn} spark={p95} sub={`${service} · target 250ms`} />
      <Card area="area-s3" label="availability" value={pct(avail, 2)} burn={availBurn} spark={availSpark} sub={`${service} · SLO 99%`} />
      <Card area="area-s4" label="error budget" value={pct(budgetRemaining, 0)} burn={budgetBurn} spark={err} sub={budgetBurn === "crit" ? `exhausted · burn ${burnX.toFixed(1)}×` : `burn ${burnX.toFixed(1)}×`} />
    </>
  );
}

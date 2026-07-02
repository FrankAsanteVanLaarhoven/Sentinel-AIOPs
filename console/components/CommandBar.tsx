"use client";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import clsx from "clsx";
import { useBoard } from "@/lib/board";
import { useLive } from "@/lib/live";
import type { TimeRange, Env, ScenarioMeta } from "@/lib/types";
import { Badge } from "./ui";

const RANGES: TimeRange[] = ["10m", "1h", "24h"];
const ENVS: Env[] = ["prod", "staging"];
// The Sentinel topology is a fixed service set; the filter focuses the board.
const SERVICES = ["frontend", "cart", "checkout", "payment", "productcatalog"];

function Segmented<T extends string>({
  value,
  options,
  onChange,
  label,
}: {
  value: T;
  options: readonly T[];
  onChange: (v: T) => void;
  label: string;
}) {
  return (
    <div
      role="group"
      aria-label={label}
      className="mono inline-flex items-center rounded-md border border-[var(--line-2)] p-0.5 bg-[var(--panel-2)]"
    >
      {options.map((o) => (
        <button
          key={o}
          onClick={() => onChange(o)}
          aria-pressed={value === o}
          className={clsx(
            "px-2 h-6 rounded text-[11px] leading-none transition-colors",
            value === o
              ? "bg-[var(--line-2)] text-[var(--pearl)]"
              : "text-[var(--mist)] hover:text-[var(--silver)]",
          )}
        >
          {o}
        </button>
      ))}
    </div>
  );
}

export function CommandBar() {
  const { env, setEnv, range, setRange, focus, setFocus, scenario, setScenario, live, setLive, demo } =
    useBoard();
  const { connected } = useLive();
  const qc = useQueryClient();
  const { data: scen } = useQuery({
    queryKey: ["scenarios"],
    queryFn: async (): Promise<{ scenarios: ScenarioMeta[] }> => {
      const res = await fetch("/api/scenarios");
      if (!res.ok) throw new Error("scenarios");
      return res.json();
    },
    enabled: demo,
    staleTime: Infinity,
  });
  const scenarios = scen?.scenarios ?? [];
  const activeScenario = scenarios.find((s) => s.id === scenario);

  return (
    <header className="sticky top-0 z-30 flex flex-wrap items-center gap-x-4 gap-y-2 px-4 h-auto min-h-14 py-2 border-b border-[var(--line)] bg-[color:color-mix(in_srgb,var(--void)_88%,transparent)] backdrop-blur-md">
      {/* brand */}
      <div className="flex items-center gap-2.5">
        <span
          className="grid place-items-center h-6 w-6 rounded-md border border-[var(--line-2)]"
          style={{ background: "radial-gradient(circle at 30% 25%, rgba(127,166,217,.5), transparent 70%)" }}
          aria-hidden
        >
          <span className="dot dot-crit" />
        </span>
        <div className="leading-tight">
          <div
            className="text-[13px] text-[var(--pearl)] tracking-tight"
            style={{ fontFamily: "var(--disp)" }}
          >
            Sentinel Console
          </div>
          <div className="mono text-[9px] text-[var(--dim)] uppercase tracking-[0.14em]">
            incident triage
          </div>
        </div>
      </div>

      <div className="h-6 w-px bg-[var(--line)]" aria-hidden />

      <Segmented value={env} options={ENVS} onChange={setEnv} label="environment" />
      {demo && (
        <Badge tone="demo" title="Board is reading the engine's seeded demo telemetry, not live infrastructure.">
          demo
        </Badge>
      )}

      {demo && scenarios.length > 0 && (
        <label
          className="mono flex items-center gap-1.5 text-[11px] text-[var(--mist)]"
          title={activeScenario ? `${activeScenario.note} (ground-truth root: ${activeScenario.root})` : "Pick an incident scenario"}
        >
          <span className="text-[var(--dim)]">scenario</span>
          <select
            value={scenario}
            onChange={(e) => setScenario(e.target.value)}
            className="mono bg-[var(--panel-2)] border border-[var(--line-2)] rounded px-1.5 h-6 text-[11px] text-[var(--silver)] focus-visible:outline-none"
          >
            {scenarios.map((s) => (
              <option key={s.id} value={s.id}>
                {s.label}
              </option>
            ))}
          </select>
        </label>
      )}

      {/* right cluster */}
      <div className="ml-auto flex flex-wrap items-center gap-x-3 gap-y-2">
        {/* service filter */}
        <label className="mono flex items-center gap-1.5 text-[11px] text-[var(--mist)]">
          <span className="text-[var(--dim)]">service</span>
          <select
            value={focus ?? ""}
            onChange={(e) => setFocus(e.target.value || null)}
            className="mono bg-[var(--panel-2)] border border-[var(--line-2)] rounded px-1.5 h-6 text-[11px] text-[var(--silver)] focus-visible:outline-none"
          >
            <option value="">all</option>
            {SERVICES.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
        </label>
        <span className="mono text-[11px] text-[var(--dim)] hidden md:inline">
          cluster <span className="text-[var(--mist)]">use1-prod</span>
        </span>

        <div className="h-6 w-px bg-[var(--line)]" aria-hidden />

        <Segmented value={range} options={RANGES} onChange={setRange} label="time range" />

        {/* live / paused */}
        <button
          onClick={() => setLive(!live)}
          aria-pressed={live}
          className={clsx(
            "mono inline-flex items-center gap-1.5 h-6 px-2 rounded-md border text-[11px] transition-colors",
            live
              ? "border-[color:color-mix(in_srgb,var(--ok)_45%,transparent)] text-[var(--ok)]"
              : "border-[var(--line-2)] text-[var(--mist)]",
          )}
          title={live ? (connected ? "Streaming live frames" : "Connecting…") : "Stream paused"}
        >
          <span
            className={clsx("dot", live && connected ? "dot-ok" : "")}
            style={{
              background: live ? (connected ? undefined : "var(--warn)") : "var(--dim)",
              animation: live && connected ? "pulse-ring 1.6s infinite" : undefined,
            }}
          />
          {live ? (connected ? "live" : "…") : "paused"}
        </button>

        <button
          onClick={() => qc.invalidateQueries()}
          className="mono h-6 px-2 rounded-md border border-[var(--line-2)] text-[11px] text-[var(--mist)] hover:text-[var(--silver)] transition-colors"
          title="Refetch all panels"
        >
          refresh
        </button>

        {/* always-on data-source citation */}
        <span className="mono text-[10px] text-[var(--dim)] hidden lg:inline">
          source:{" "}
          <span className={demo ? "text-[var(--warn)]" : "text-[var(--ice)]"}>
            {demo ? "DEMO · seeded" : "Prometheus/Tempo"}
          </span>
        </span>
      </div>
    </header>
  );
}

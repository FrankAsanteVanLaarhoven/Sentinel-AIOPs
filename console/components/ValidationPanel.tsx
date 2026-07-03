"use client";
import { useQuery } from "@tanstack/react-query";
import type {
  Validation,
  ValidationLayer,
  DetectorCard,
  LocalizationCard,
  ValidationCard,
} from "@/lib/types";
import { Panel, PanelMessage } from "./Panel";

async function fetchValidation(): Promise<Validation> {
  const r = await fetch("/api/validation");
  if (!r.ok) throw new Error(`validation ${r.status}`);
  return r.json();
}

const ACCENT: Record<ValidationLayer["kind"], string> = {
  learned: "var(--ice)",
  deterministic: "var(--ok)",
  empirical: "var(--warn)",
};

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex flex-col gap-0.5">
      <span className="mono tnum text-[16px] text-[var(--pearl)] leading-none">{value}</span>
      <span className="mono text-[8px] uppercase tracking-[0.1em] text-[var(--mist)]">{label}</span>
    </div>
  );
}

function Source({ label }: { label: string }) {
  const fresh = label.startsWith("reproduced");
  return (
    <span
      className="mono text-[9px] px-1.5 py-0.5 rounded self-start"
      style={{
        color: fresh ? "var(--ok)" : "var(--mist)",
        border: `1px solid ${fresh ? "color-mix(in srgb, var(--ok) 40%, transparent)" : "var(--line-2)"}`,
      }}
      title={fresh ? "Regenerated from source on this machine" : "Documented, reproducible envelope"}
    >
      {label}
    </span>
  );
}

function Modes({ title, items }: { title: string; items: string[] }) {
  return (
    <details className="group mt-auto">
      <summary className="mono text-[9px] text-[var(--dim)] hover:text-[var(--mist)] list-none flex items-center gap-1 select-none">
        <span className="group-open:rotate-90 transition-transform inline-block">▸</span>
        {title} ({items.length})
      </summary>
      <ul className="mt-1.5 flex flex-col gap-1 pl-3">
        {items.map((f, i) => (
          <li key={i} className="mono text-[9px] leading-relaxed text-[var(--mist)] list-disc list-outside">
            {f}
          </li>
        ))}
      </ul>
    </details>
  );
}

function DetectorRow({ d }: { d: DetectorCard }) {
  const pct = (v: number) => `${(v * 100).toFixed(1)}%`;
  const m = d.metrics;
  return (
    <div className="rounded-md border border-[var(--line)] px-2 py-1.5 flex flex-col gap-1">
      <div className="flex items-center justify-between gap-2">
        <span className="mono text-[10px] text-[var(--pearl)]">{d.name}</span>
        <Source label={d.source} />
      </div>
      <div className="mono tnum text-[10px] text-[var(--silver)] flex flex-wrap gap-x-2.5 gap-y-0.5">
        <span>P {pct(m.precision)}</span>
        <span>R {pct(m.recall)}</span>
        <span>F1 {m.f1.toFixed(3)}</span>
        {m.roc_auc != null && <span className="text-[var(--mist)]">AUC {m.roc_auc.toFixed(3)}</span>}
        {m.f1_point_adjusted != null && (
          <span className="text-[var(--mist)]" title="point-adjusted F1 (SMD convention)">
            PA-F1 {m.f1_point_adjusted.toFixed(2)}
          </span>
        )}
      </div>
      <div className="mono text-[8px] text-[var(--dim)] truncate" title={d.dataset}>
        {d.model} · {d.dataset}
      </div>
    </div>
  );
}

function Detection({ detectors }: { detectors: DetectorCard[] }) {
  const notes = detectors.map((d) => d.note).filter((n): n is string => !!n);
  return (
    <>
      <div className="flex flex-col gap-1.5">
        {detectors.map((d) => (
          <DetectorRow key={d.name} d={d} />
        ))}
      </div>
      {notes.length > 0 && <Modes title="caveats" items={notes} />}
    </>
  );
}

function Localization({ c }: { c: LocalizationCard }) {
  return (
    <>
      <div className="flex items-center gap-2">
        <span className="dot dot-ok" />
        <span className="mono text-[11px] text-[var(--ok)]">no model weights · replayable</span>
      </div>
      <div className="mono text-[10px] leading-relaxed text-[var(--silver)]">{c.rule}</div>
      <p className="mono text-[9px] leading-relaxed text-[var(--mist)] mt-auto">{c.note}</p>
    </>
  );
}

function ValidationBody({ c }: { c: ValidationCard }) {
  return (
    <>
      <div className="grid grid-cols-3 gap-2">
        <Stat label="recall@1" value={c.recall_at_1.toFixed(3)} />
        <Stat label="recall@3" value={c.recall_at_3.toFixed(3)} />
        <Stat label="coverage" value={c.detection_coverage.toFixed(3)} />
      </div>
      <div className="mono text-[9px] text-[var(--dim)]">
        {c.incidents} real incidents · <span className="text-[var(--silver)]">{c.dataset}</span>
      </div>
      <Source label={c.source} />
      <Modes title="failure modes" items={c.failure_modes} />
    </>
  );
}

function LayerCard({ layer }: { layer: ValidationLayer }) {
  const accent = ACCENT[layer.kind];
  return (
    <div className="rounded-lg border border-[var(--line)] bg-[var(--panel-2)] overflow-hidden flex flex-col">
      <div style={{ height: 2, background: accent }} />
      <div className="p-3 flex flex-col gap-2 flex-1 min-h-[188px]">
        <div className="flex items-center justify-between">
          <span className="text-[13px] text-[var(--pearl)]" style={{ fontFamily: "var(--disp)" }}>
            {layer.title}
          </span>
          <span
            className="mono text-[9px] px-1.5 py-0.5 rounded"
            style={{ color: accent, border: `1px solid ${accent}` }}
          >
            {layer.kind}
          </span>
        </div>
        <p className="mono text-[10px] leading-relaxed text-[var(--mist)]">{layer.subtitle}</p>
        {layer.id === "detection" && <Detection detectors={layer.detectors ?? []} />}
        {layer.id === "localization" && <Localization c={layer.card as LocalizationCard} />}
        {layer.id === "validation" && <ValidationBody c={layer.card as ValidationCard} />}
      </div>
    </div>
  );
}

export function ValidationPanel() {
  const { data, isLoading, isError } = useQuery({
    queryKey: ["validation"],
    queryFn: fetchValidation,
    staleTime: 60 * 60 * 1000,
  });

  return (
    <Panel title="Validation — how we know it works" right="three-layer · honest" className="area-val min-h-[260px]">
      {isLoading && <PanelMessage kind="loading" title="Loading validation cards…" />}
      {isError && <PanelMessage kind="error" detail="Could not reach the Sentinel engine." />}
      {data && (
        <div className="flex flex-col gap-3">
          <p className="mono text-[10px] leading-relaxed text-[var(--silver)] border-l-2 border-[var(--line-2)] pl-2.5">
            {data.principle}
          </p>
          <div className="grid gap-3 md:grid-cols-3">
            {data.layers.map((l) => (
              <LayerCard key={l.id} layer={l} />
            ))}
          </div>
          <p className="mono text-[9px] text-[var(--dim)] text-right">
            served from committed model cards · no training or validation run to view this
          </p>
        </div>
      )}
    </Panel>
  );
}

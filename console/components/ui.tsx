import clsx from "clsx";
import type { ReactNode } from "react";

export function StatusDot({
  status,
  className,
}: {
  status: "ok" | "warn" | "root" | "crit";
  className?: string;
}) {
  const cls =
    status === "ok" ? "dot-ok" : status === "warn" ? "dot-warn" : "dot-crit";
  return <span className={clsx("dot", cls, className)} aria-hidden />;
}

export function Badge({
  children,
  tone = "neutral",
  title,
}: {
  children: ReactNode;
  tone?: "neutral" | "ok" | "warn" | "crit" | "ice" | "demo";
  title?: string;
}) {
  const tones: Record<string, string> = {
    neutral: "text-[var(--silver)] border-[var(--line-2)]",
    ok: "text-[var(--ok)] border-[color:color-mix(in_srgb,var(--ok)_45%,transparent)]",
    warn: "text-[var(--warn)] border-[color:color-mix(in_srgb,var(--warn)_45%,transparent)]",
    crit: "text-[var(--crit)] border-[color:color-mix(in_srgb,var(--crit)_50%,transparent)]",
    ice: "text-[var(--ice)] border-[color:color-mix(in_srgb,var(--ice)_45%,transparent)]",
    demo: "text-[var(--warn)] border-[color:color-mix(in_srgb,var(--warn)_55%,transparent)] bg-[color:color-mix(in_srgb,var(--warn)_10%,transparent)]",
  };
  return (
    <span
      title={title}
      className={clsx(
        "mono inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-[10px] uppercase tracking-[0.08em] border leading-none",
        tones[tone],
      )}
    >
      {children}
    </span>
  );
}

/** Confidence chip — a small filled meter + value. Honest: it's a heuristic. */
export function ConfidenceChip({ value }: { value: number }) {
  const pct = Math.round(value * 100);
  const tone = value >= 0.8 ? "var(--ok)" : value >= 0.6 ? "var(--warn)" : "var(--crit)";
  return (
    <span
      className="mono inline-flex items-center gap-1.5 text-[11px] text-[var(--silver)]"
      title="Heuristic confidence: separation of the root's error from the next-loudest service, plus change-correlation. Not a probability."
    >
      <span className="text-[var(--mist)]">confidence</span>
      <span
        className="relative h-1.5 w-12 rounded-full overflow-hidden"
        style={{ background: "rgba(255,255,255,.08)" }}
      >
        <span
          className="absolute inset-y-0 left-0 rounded-full"
          style={{ width: `${pct}%`, background: tone }}
        />
      </span>
      <span style={{ color: tone }}>{pct}%</span>
    </span>
  );
}

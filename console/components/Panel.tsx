import clsx from "clsx";
import type { ReactNode } from "react";

/** The container every visualization sits in. Hairline border, mono meta,
 * Sora title, optional dotted "Foundry" grid background. */
export function Panel({
  title,
  right,
  children,
  className,
  gridBg = false,
  accent,
  bodyClassName,
}: {
  title: string;
  right?: ReactNode;
  children: ReactNode;
  className?: string;
  gridBg?: boolean;
  accent?: "ok" | "warn" | "crit";
  bodyClassName?: string;
}) {
  return (
    <section
      className={clsx(
        "rounded-lg border border-[var(--line)] bg-[var(--panel)] flex flex-col min-h-0 overflow-hidden",
        className,
      )}
      style={
        accent
          ? { boxShadow: `inset 3px 0 0 0 var(--${accent})` }
          : undefined
      }
    >
      <header className="flex items-center justify-between gap-3 px-4 h-10 border-b border-[var(--line)] shrink-0">
        <h3
          className="text-[13px] tracking-tight text-[var(--pearl)] truncate"
          style={{ fontFamily: "var(--disp)" }}
        >
          {title}
        </h3>
        <div className="mono text-[11px] text-[var(--mist)] shrink-0">{right}</div>
      </header>
      <div
        className={clsx(
          "p-3 flex-1 min-h-0 relative",
          gridBg && "panel-grid-bg",
          bodyClassName,
        )}
      >
        {children}
      </div>
    </section>
  );
}

/** Consistent loading / empty / error content in the velvet style. */
export function PanelMessage({
  kind,
  title,
  detail,
}: {
  kind: "loading" | "empty" | "error";
  title?: string;
  detail?: string;
}) {
  if (kind === "loading") {
    return (
      <div className="h-full w-full flex flex-col gap-2 min-h-24" aria-busy="true">
        <div className="skeleton h-3 w-1/3" />
        <div className="skeleton flex-1 min-h-16" />
      </div>
    );
  }
  const color = kind === "error" ? "text-[var(--crit)]" : "text-[var(--mist)]";
  return (
    <div className="h-full w-full min-h-24 flex flex-col items-center justify-center text-center gap-1 px-4">
      <div className={clsx("mono text-[12px]", color)}>
        {title ?? (kind === "error" ? "Signal unavailable" : "No data")}
      </div>
      {detail && (
        <div className="mono text-[11px] text-[var(--dim)] max-w-sm">{detail}</div>
      )}
    </div>
  );
}

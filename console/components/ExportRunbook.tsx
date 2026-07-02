"use client";
import { useState } from "react";

// Minimal Markdown -> HTML for the engine's runbook shape (headings, bold,
// inline code, bullet lists, one table, hr, paragraphs). No dependency.
function mdToHtml(md: string): string {
  const esc = (s: string) =>
    s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  const inline = (s: string) =>
    esc(s)
      .replace(/`([^`]+)`/g, "<code>$1</code>")
      .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
      .replace(/_([^_]+)_/g, "<em>$1</em>");

  const lines = md.split("\n");
  const out: string[] = [];
  let i = 0;
  const flushList = (buf: string[]) => {
    if (buf.length) out.push(`<ul>${buf.map((b) => `<li>${inline(b)}</li>`).join("")}</ul>`);
    buf.length = 0;
  };
  const listBuf: string[] = [];

  while (i < lines.length) {
    const line = lines[i];
    if (/^\|/.test(line) && /^\|/.test(lines[i + 1] ?? "")) {
      flushList(listBuf);
      const rows: string[] = [];
      while (i < lines.length && /^\|/.test(lines[i])) {
        rows.push(lines[i]);
        i++;
      }
      const cells = (r: string) => r.split("|").slice(1, -1).map((c) => c.trim());
      const head = cells(rows[0]);
      const body = rows.slice(2).map(cells);
      out.push(
        `<table><thead><tr>${head.map((h) => `<th>${inline(h)}</th>`).join("")}</tr></thead><tbody>${body
          .map((r) => `<tr>${r.map((c) => `<td>${inline(c)}</td>`).join("")}</tr>`)
          .join("")}</tbody></table>`,
      );
      continue;
    }
    if (/^### /.test(line)) { flushList(listBuf); out.push(`<h3>${inline(line.slice(4))}</h3>`); }
    else if (/^## /.test(line)) { flushList(listBuf); out.push(`<h2>${inline(line.slice(3))}</h2>`); }
    else if (/^# /.test(line)) { flushList(listBuf); out.push(`<h1>${inline(line.slice(2))}</h1>`); }
    else if (/^- /.test(line)) { listBuf.push(line.slice(2)); }
    else if (/^---\s*$/.test(line)) { flushList(listBuf); out.push("<hr/>"); }
    else if (line.trim() === "") { flushList(listBuf); }
    else { flushList(listBuf); out.push(`<p>${inline(line)}</p>`); }
    i++;
  }
  flushList(listBuf);
  return out.join("\n");
}

const PRINT_CSS = `
  :root { color-scheme: light; }
  * { box-sizing: border-box; }
  body { font: 14px/1.6 -apple-system,BlinkMacSystemFont,"Segoe UI",Inter,system-ui,sans-serif;
    color:#1a1f2b; background:#fff; max-width:760px; margin:40px auto; padding:0 28px; }
  h1 { font-size:24px; letter-spacing:-.02em; border-bottom:2px solid #ff6a4d; padding-bottom:8px; }
  h2 { font-size:16px; margin-top:28px; color:#0b0e15; border-bottom:1px solid #e6e8ee; padding-bottom:5px; }
  h3 { font-size:14px; margin-top:18px; }
  code { font:12px "IBM Plex Mono",ui-monospace,monospace; background:#f2f3f7; padding:1px 5px; border-radius:4px; }
  table { border-collapse:collapse; width:100%; margin:12px 0; font-size:12.5px; }
  th,td { border:1px solid #e2e5ec; padding:6px 9px; text-align:left; }
  th { background:#f7f8fb; font-weight:600; }
  hr { border:none; border-top:1px solid #e6e8ee; margin:24px 0; }
  em { color:#6b7280; font-style:normal; font-size:12px; }
  ul { padding-left:20px; }
  @media print { body { margin:0; max-width:none; } }
`;

export function ExportRunbook({ scenario }: { scenario: string }) {
  const [busy, setBusy] = useState<null | "md" | "print">(null);

  const fetchMd = async () => {
    const r = await fetch(`/api/runbook?scenario=${encodeURIComponent(scenario)}`);
    if (!r.ok) throw new Error("runbook");
    return (await r.json()).markdown as string;
  };

  const download = async () => {
    setBusy("md");
    try {
      const md = await fetchMd();
      const url = URL.createObjectURL(new Blob([md], { type: "text/markdown" }));
      const a = document.createElement("a");
      a.href = url;
      a.download = `runbook-${scenario}.md`;
      a.click();
      URL.revokeObjectURL(url);
    } finally {
      setBusy(null);
    }
  };

  const print = async () => {
    setBusy("print");
    try {
      const md = await fetchMd();
      const w = window.open("", "_blank", "width=820,height=1000");
      if (!w) return;
      w.document.write(
        `<!doctype html><html><head><meta charset="utf-8"><title>Runbook — ${scenario}</title><style>${PRINT_CSS}</style></head><body>${mdToHtml(md)}</body></html>`,
      );
      w.document.close();
      w.focus();
      setTimeout(() => w.print(), 300);
    } finally {
      setBusy(null);
    }
  };

  const btn =
    "mono text-[10px] h-6 px-2 rounded-md border border-[var(--line-2)] text-[var(--silver)] hover:text-[var(--pearl)] hover:border-[var(--ice)] transition-colors disabled:opacity-50";

  return (
    <span className="flex items-center gap-1.5">
      <button onClick={download} disabled={!!busy} className={btn} title="Download the incident runbook as Markdown">
        {busy === "md" ? "…" : "⤓ runbook"}
      </button>
      <button onClick={print} disabled={!!busy} className={btn} title="Open a printable runbook (Save as PDF)">
        {busy === "print" ? "…" : "⎙ PDF"}
      </button>
    </span>
  );
}

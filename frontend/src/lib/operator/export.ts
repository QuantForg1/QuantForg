/** Operator report export helpers — CSV + printable institutional PDF (browser print). */

export function downloadText(filename: string, content: string, mime: string) {
  const blob = new Blob([content], { type: mime });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

export function toCsv(
  rows: Array<Record<string, string | number | null | undefined>>,
): string {
  if (!rows.length) return "";
  const headers = Object.keys(rows[0]!);
  const esc = (v: unknown) => {
    const s = v == null ? "" : String(v);
    return /["\n,]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
  };
  return [
    headers.join(","),
    ...rows.map((r) => headers.map((h) => esc(r[h])).join(",")),
  ].join("\n");
}

/** Open a print-ready institutional report; user saves as PDF. */
export function exportPrintablePdf(opts: {
  title: string;
  subtitle?: string;
  sections: Array<{ heading: string; html: string }>;
}) {
  const win = window.open("", "_blank", "noopener,noreferrer,width=960,height=720");
  if (!win) return;
  const body = opts.sections
    .map(
      (s) =>
        `<section style="margin:0 0 24px"><h2 style="font:600 13px/1.2 IBM Plex Sans,system-ui,sans-serif;letter-spacing:.08em;text-transform:uppercase;color:#94a3b8;margin:0 0 8px">${escapeHtml(s.heading)}</h2><div style="font:13px/1.5 IBM Plex Sans,system-ui,sans-serif;color:#e5e7eb">${s.html}</div></section>`,
    )
    .join("");
  win.document.write(`<!doctype html><html><head><meta charset="utf-8"/><title>${escapeHtml(opts.title)}</title>
<style>
  @page { margin: 18mm; }
  body { margin:0; padding:28px; background:#111827; color:#e5e7eb; font-family:IBM Plex Sans,system-ui,sans-serif; }
  h1 { font:600 22px/1.2 IBM Plex Sans,system-ui,sans-serif; margin:0 0 4px; color:#00d4e0; }
  .sub { color:#94a3b8; font-size:12px; margin-bottom:28px; }
  table { width:100%; border-collapse:collapse; font-size:12px; }
  th,td { border-bottom:1px solid #334155; padding:6px 8px; text-align:left; }
  th { color:#94a3b8; font-weight:600; text-transform:uppercase; letter-spacing:.06em; font-size:10px; }
  .mono { font-family:IBM Plex Mono,ui-monospace,monospace; }
</style></head><body>
  <h1>${escapeHtml(opts.title)}</h1>
  <p class="sub">${escapeHtml(opts.subtitle || "QuantForg Operator OS · LIVE data only")}</p>
  ${body}
  <script>window.onload=()=>{window.print();}</script>
</body></html>`);
  win.document.close();
}

function escapeHtml(s: string): string {
  return s
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

export function kvTable(
  rows: Array<[string, string | number | null | undefined]>,
): string {
  return `<table><tbody>${rows
    .map(
      ([k, v]) =>
        `<tr><th>${escapeHtml(k)}</th><td class="mono">${escapeHtml(v == null ? "—" : String(v))}</td></tr>`,
    )
    .join("")}</tbody></table>`;
}

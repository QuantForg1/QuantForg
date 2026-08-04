"use client";

import { useMemo, useState } from "react";
import { useEffect } from "react";
import { DeskEmpty } from "@/components/desk/primitives";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  clearApiRequestSamples,
  exportApiRequestSamplesCsv,
  listApiRequestSamples,
  subscribeApiRequestSamples,
  type ApiRequestSample,
} from "@/lib/api/request-log";
import { Search } from "lucide-react";

/** Client-side API Inspector — LIVE samples from apiFetch telemetry. */
export function ApiInspectorWorkspace() {
  const [rows, setRows] = useState<ApiRequestSample[]>(() => listApiRequestSamples());
  const [q, setQ] = useState("");
  const [sort, setSort] = useState<"latency" | "time">("latency");

  useEffect(() => subscribeApiRequestSamples(setRows), []);

  const filtered = useMemo(() => {
    const needle = q.trim().toLowerCase();
    let list = rows;
    if (needle) {
      list = list.filter(
        (r) =>
          r.path.toLowerCase().includes(needle) ||
          r.method.toLowerCase().includes(needle) ||
          String(r.status).includes(needle) ||
          (r.error || "").toLowerCase().includes(needle),
      );
    }
    if (sort === "latency") {
      return [...list].sort((a, b) => b.latencyMs - a.latencyMs);
    }
    return list;
  }, [q, rows, sort]);

  const exportCsv = () => {
    const csv = exportApiRequestSamplesCsv(filtered);
    const blob = new Blob([csv], { type: "text/csv;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `quantforg-api-inspector-${Date.now()}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="space-y-4">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
        <div className="relative max-w-md flex-1">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[var(--fg-subtle)]" />
          <Input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Search route, status, error…"
            className="pl-9"
            aria-label="Search API samples"
          />
        </div>
        <div className="flex flex-wrap gap-2">
          <Button
            size="sm"
            variant={sort === "latency" ? "default" : "outline"}
            onClick={() => setSort("latency")}
          >
            Sort latency
          </Button>
          <Button
            size="sm"
            variant={sort === "time" ? "default" : "outline"}
            onClick={() => setSort("time")}
          >
            Sort time
          </Button>
          <Button size="sm" variant="outline" onClick={exportCsv} disabled={!filtered.length}>
            Export CSV
          </Button>
          <Button
            size="sm"
            variant="ghost"
            onClick={() => clearApiRequestSamples()}
            disabled={!rows.length}
          >
            Clear
          </Button>
        </div>
      </div>

      {!filtered.length ? (
        <DeskEmpty
          icon={Search}
          title="No API samples yet"
          description="Navigate the desk — each apiFetch records route, status, latency, retries, and timeouts here."
        />
      ) : (
        <div className="overflow-x-auto border border-[var(--border)]">
          <table className="min-w-full text-left text-[12px]">
            <thead className="bg-[var(--surface)] text-[10px] uppercase tracking-[0.1em] text-[var(--fg-subtle)]">
              <tr>
                <th className="px-3 py-2">Time</th>
                <th className="px-3 py-2">Method</th>
                <th className="px-3 py-2">Route</th>
                <th className="px-3 py-2">Status</th>
                <th className="px-3 py-2">Latency</th>
                <th className="px-3 py-2">Size</th>
                <th className="px-3 py-2">Retries</th>
                <th className="px-3 py-2">Flags</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((r) => (
                <tr key={r.id} className="border-t border-[var(--border)]">
                  <td className="px-3 py-2 font-mono text-[10px] text-[var(--fg-muted)]">
                    {r.at.slice(11, 19)}
                  </td>
                  <td className="px-3 py-2 font-mono">{r.method}</td>
                  <td className="max-w-[28rem] truncate px-3 py-2 font-mono text-[var(--fg)]">
                    {r.path}
                  </td>
                  <td className="px-3 py-2">
                    <Badge
                      tone={
                        r.status >= 200 && r.status < 400
                          ? "success"
                          : r.status === 408 || r.timedOut
                            ? "warning"
                            : "danger"
                      }
                      className="h-5 px-1.5 text-[10px]"
                    >
                      {r.status || "—"}
                    </Badge>
                  </td>
                  <td className="px-3 py-2 tabular">{r.latencyMs} ms</td>
                  <td className="px-3 py-2 tabular">
                    {r.sizeBytes == null ? "—" : `${r.sizeBytes} B`}
                  </td>
                  <td className="px-3 py-2 tabular">{r.retries}</td>
                  <td className="px-3 py-2 text-[var(--fg-muted)]">
                    {r.timedOut ? "timeout" : r.error ? r.error.slice(0, 48) : "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

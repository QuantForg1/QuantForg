"use client";

import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { DeskEmpty, DeskError, DeskSkeleton } from "@/components/desk/primitives";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { executionApi, iteOpsApi, opsApi } from "@/lib/api/endpoints";
import { asList, asRecord, str } from "@/lib/desk";
import { listMonitoredErrors } from "@/lib/observability/error-monitor";
import { BookOpen, Copy, Download, Search } from "lucide-react";

type Filter =
  | "all"
  | "gateway"
  | "oms"
  | "pme"
  | "risk"
  | "scanner"
  | "execution"
  | "errors";

function rowText(row: Record<string, unknown>): string {
  try {
    return JSON.stringify(row);
  } catch {
    return String(row);
  }
}

function matchesFilter(text: string, filter: Filter): boolean {
  if (filter === "all") return true;
  if (filter === "errors") return /error|fail|reject|timeout/i.test(text);
  return text.toLowerCase().includes(filter);
}

/** LIVE operational log viewer — journal + audit + client errors. */
export function LogViewerWorkspace() {
  const [filter, setFilter] = useState<Filter>("all");
  const [q, setQ] = useState("");

  const journalQ = useQuery({
    queryKey: ["execution-journal", "logs"],
    queryFn: () => executionApi.journal(120),
    staleTime: 15_000,
    refetchInterval: 25_000,
    retry: false,
  });
  const iteAuditQ = useQuery({
    queryKey: ["ite-ops-audit", "logs"],
    queryFn: () => iteOpsApi.audit(100),
    staleTime: 15_000,
    refetchInterval: 25_000,
    retry: false,
  });
  const opsAuditQ = useQuery({
    queryKey: ["ops-audit", "logs"],
    queryFn: () => opsApi.audit(),
    staleTime: 20_000,
    refetchInterval: 40_000,
    retry: false,
  });

  const rows = useMemo(() => {
    const sources = [
      ...asList(
        asRecord(journalQ.data).items ||
          asRecord(journalQ.data).events ||
          asRecord(journalQ.data).journal ||
          journalQ.data,
      ).map(asRecord),
      ...asList(
        asRecord(iteAuditQ.data).items ||
          asRecord(iteAuditQ.data).events ||
          asRecord(iteAuditQ.data).audit ||
          iteAuditQ.data,
      ).map(asRecord),
      ...asList(
        asRecord(opsAuditQ.data).items ||
          asRecord(opsAuditQ.data).events ||
          asRecord(opsAuditQ.data).audit ||
          opsAuditQ.data,
      ).map(asRecord),
      ...listMonitoredErrors().map((e) =>
        asRecord({
          at: e.timestamp || "",
          source: "client-error",
          message: e.message,
          kind: e.kind,
          path: e.path,
          status: e.status,
        }),
      ),
    ] as Record<string, unknown>[];
    const needle = q.trim().toLowerCase();
    return sources
      .map((r) => ({ row: r, text: rowText(r) }))
      .filter(({ text }) => matchesFilter(text, filter))
      .filter(({ text }) => !needle || text.toLowerCase().includes(needle))
      .slice(0, 250);
  }, [filter, iteAuditQ.data, journalQ.data, opsAuditQ.data, q]);

  const loading =
    (journalQ.isLoading || iteAuditQ.isLoading) && rows.length === 0;
  const errored = journalQ.isError && iteAuditQ.isError && opsAuditQ.isError;

  const copyAll = async () => {
    await navigator.clipboard.writeText(rows.map((r) => r.text).join("\n"));
  };
  const download = () => {
    const blob = new Blob([rows.map((r) => r.text).join("\n")], {
      type: "application/jsonl",
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `quantforg-logs-${Date.now()}.jsonl`;
    a.click();
    URL.revokeObjectURL(url);
  };

  if (loading) return <DeskSkeleton rows={8} />;
  if (errored) {
    return (
      <DeskError
        message="Unable to load operational logs."
        onRetry={() => {
          void journalQ.refetch();
          void iteAuditQ.refetch();
          void opsAuditQ.refetch();
        }}
      />
    );
  }

  const filters: Filter[] = [
    "all",
    "gateway",
    "oms",
    "pme",
    "risk",
    "scanner",
    "execution",
    "errors",
  ];

  return (
    <div className="space-y-4">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
        <div className="relative max-w-md flex-1">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[var(--fg-subtle)]" />
          <Input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            className="pl-9"
            placeholder="Search logs…"
            aria-label="Search logs"
          />
        </div>
        <div className="flex flex-wrap gap-2">
          {filters.map((f) => (
            <Button
              key={f}
              size="sm"
              variant={filter === f ? "default" : "outline"}
              onClick={() => setFilter(f)}
            >
              {f}
            </Button>
          ))}
          <Button size="sm" variant="outline" onClick={() => void copyAll()} disabled={!rows.length}>
            <Copy className="mr-1 h-3.5 w-3.5" />
            Copy
          </Button>
          <Button size="sm" variant="outline" onClick={download} disabled={!rows.length}>
            <Download className="mr-1 h-3.5 w-3.5" />
            Download
          </Button>
        </div>
      </div>

      {!rows.length ? (
        <DeskEmpty
          icon={BookOpen}
          title="No matching log lines"
          description="LIVE journal and audit events appear when the platform is active."
        />
      ) : (
        <ul className="max-h-[70vh] space-y-0 overflow-y-auto border border-[var(--border)] bg-[var(--surface)] font-mono text-[11px]">
          {rows.map(({ row, text }, i) => (
            <li
              key={`${str(row.id, String(i))}-${i}`}
              className="border-b border-[var(--border)] px-3 py-2 text-[var(--fg-muted)]"
            >
              <div className="mb-1 flex items-center gap-2">
                <Badge tone="neutral" className="h-4 px-1 text-[9px]">
                  {str(row.source || row.kind || "event")}
                </Badge>
                <span className="text-[10px] text-[var(--fg-subtle)]">
                  {str(row.at || row.timestamp || row.created_at, "")}
                </span>
              </div>
              <pre className="whitespace-pre-wrap break-all text-[var(--fg)]">{text}</pre>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

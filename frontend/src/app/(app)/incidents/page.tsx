"use client";

import { useQuery } from "@tanstack/react-query";
import { AlertTriangle } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { DeskEmpty, DeskError, DeskSkeleton } from "@/components/desk/primitives";
import { WorkspacePage } from "@/components/layout/workspace-page";
import { iteReliabilityApi } from "@/lib/api/endpoints";
import { ApiError } from "@/lib/api/client";
import { asList, asRecord, str } from "@/lib/desk";

export default function IncidentsPage() {
  const q = useQuery({
    queryKey: ["ite-reliability-incidents"],
    queryFn: () => iteReliabilityApi.incidents(),
    staleTime: 15_000,
    refetchInterval: 30_000,
    retry: false,
  });

  const rows = asList(asRecord(q.data).incidents ?? asRecord(q.data).items).map(
    asRecord,
  );

  return (
    <WorkspacePage
      title="Incidents"
      description="Active reliability incidents from production observability."
      icon={AlertTriangle}
      actionLabel="Open Monitoring"
      actionHref="/monitoring"
    >
      {q.isLoading ? <DeskSkeleton rows={4} /> : null}
      {q.isError ? (
        <DeskError
          message={
            q.error instanceof ApiError
              ? q.error.message
              : "Incidents unavailable (OWNER/ADMIN · /ite/reliability/incidents)."
          }
        />
      ) : null}
      {!q.isLoading && !q.isError && rows.length === 0 ? (
        <DeskEmpty
          icon={AlertTriangle}
          title="No active incidents"
          description="Reliability plane reports a clear incident queue."
          actionLabel="Open Monitoring"
          actionHref="/monitoring"
        />
      ) : null}
      {!q.isLoading && !q.isError && rows.length > 0 ? (
        <ul className="divide-y divide-[var(--border)] border border-[var(--border)] bg-[var(--surface)]">
          {rows.map((row, i) => (
            <li
              key={str(row.id, `incident-${i}`)}
              className="flex flex-wrap items-start gap-2 px-3 py-2.5"
            >
              <Badge
                tone={
                  str(row.severity, str(row.status)).toLowerCase().includes("crit")
                    ? "danger"
                    : "warning"
                }
                className="text-[9px] uppercase"
              >
                {str(row.severity, str(row.status, "open"))}
              </Badge>
              <div className="min-w-0 flex-1">
                <div className="text-sm text-[var(--fg)]">
                  {str(row.title, str(row.message, str(row.kind, "Incident")))}
                </div>
                <div className="font-mono text-[10px] text-[var(--fg-subtle)]">
                  {str(row.opened_at, str(row.created_at, str(row.as_of, "—")))}
                </div>
              </div>
            </li>
          ))}
        </ul>
      ) : null}
    </WorkspacePage>
  );
}

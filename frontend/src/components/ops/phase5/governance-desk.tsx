"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { institutionalOpsApi } from "@/lib/api/endpoints";
import { asList, asRecord, str } from "@/lib/desk";
import { Button } from "@/components/ui/button";
import {
  Phase5Banner,
  Phase5Empty,
  Phase5Error,
  Phase5Loading,
  Phase5ModuleNav,
  Phase5Stat,
  Phase5TabBar,
} from "./shared";

type Tab = "queue" | "audit" | "export";

const TABS: { id: Tab; label: string }[] = [
  { id: "queue", label: "Approval queue" },
  { id: "audit", label: "Audit trail" },
  { id: "export", label: "Export / links" },
];

export function Phase5GovernanceDesk() {
  const [tab, setTab] = useState<Tab>("queue");
  const q = useQuery({
    queryKey: ["p5-governance"],
    queryFn: institutionalOpsApi.governance,
    retry: false,
    staleTime: 10_000,
  });

  if (q.isLoading) return <Phase5Loading />;
  if (q.isError) {
    return <Phase5Error message="Governance summary unavailable." />;
  }

  const data = asRecord(q.data);
  const queue = asList(data.pending_approvals);
  const events = asList(data.audit_events);

  return (
    <div>
      <Phase5ModuleNav current="/governance" />
      <Phase5Banner>
        Unified read-only approval queue across ISLM / IRDP / QSF. Audit events are
        immutable here — secrets redacted. Unauthorized modification or deletion is
        not exposed.
      </Phase5Banner>
      <Phase5TabBar tabs={TABS} value={tab} onChange={setTab} />

      <div className="mb-4 grid gap-3 sm:grid-cols-3">
        <Phase5Stat label="Pending approvals" value={queue.length} />
        <Phase5Stat label="Audit events" value={events.length} />
        <Phase5Stat
          label="Secrets redacted"
          value={data.secrets_redacted === false ? "no" : "yes"}
        />
      </div>

      {tab === "queue" &&
        (queue.length === 0 ? (
          <Phase5Empty message="No pending cross-module approvals." />
        ) : (
          <ul className="divide-y divide-border/50 rounded-md border border-border/60">
            {queue.map((item, i) => {
              const row = asRecord(item);
              return (
                <li key={i} className="px-3 py-2 text-sm">
                  <div className="font-medium">
                    {str(row.source)} · {str(row.id) || `item-${i + 1}`}
                  </div>
                  <div className="text-xs text-muted-foreground">
                    {str(row.status)} — target {str(row.target) || "—"}
                  </div>
                </li>
              );
            })}
          </ul>
        ))}

      {tab === "audit" &&
        (events.length === 0 ? (
          <Phase5Empty message="Audit ledger empty for this environment — honest empty state." />
        ) : (
          <ul className="divide-y divide-border/50 rounded-md border border-border/60">
            {events.slice(0, 50).map((item, i) => {
              const row = asRecord(item);
              return (
                <li key={i} className="px-3 py-2 text-sm">
                  <div className="font-medium">
                    {str(row.action) || str(row.event_type) || `Event ${i + 1}`}
                  </div>
                  <div className="text-xs text-muted-foreground">
                    {str(row.actor) || str(row.user) || "system"} ·{" "}
                    {str(row.timestamp) || str(row.created_at) || "—"}
                  </div>
                </li>
              );
            })}
          </ul>
        ))}

      {tab === "export" && (
        <div className="flex flex-wrap gap-2">
          <Button size="sm" variant="secondary" asChild>
            <Link href="/audit-governance">Audit governance desk</Link>
          </Button>
          <Button size="sm" variant="secondary" asChild>
            <Link href="/institutional-strategy-lifecycle">ISLM</Link>
          </Button>
          <Button size="sm" variant="secondary" asChild>
            <Link href="/institutional-release">IRDP</Link>
          </Button>
        </div>
      )}
    </div>
  );
}

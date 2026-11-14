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

type Tab = "active" | "recovery" | "sources";

const TABS: { id: Tab; label: string }[] = [
  { id: "active", label: "Active" },
  { id: "recovery", label: "Recovery rules" },
  { id: "sources", label: "Sources" },
];

export function Phase5IncidentDesk() {
  const [tab, setTab] = useState<Tab>("active");
  const q = useQuery({
    queryKey: ["p5-incidents"],
    queryFn: institutionalOpsApi.incidents,
    retry: false,
    staleTime: 10_000,
  });

  if (q.isLoading) return <Phase5Loading />;
  if (q.isError) {
    return <Phase5Error message="Incident center overview unavailable." />;
  }

  const data = asRecord(q.data);
  const incidents = asList(data.incidents);
  const recovery = asRecord(data.recovery_rules);

  return (
    <div>
      <Phase5ModuleNav current="/incident-center" />
      <Phase5Banner tone="warn">
        Recovery is idempotent and safe. Never automatically resend an order when
        execution state is uncertain — reconcile with MT5 evidence first. Never
        restart in a way that bypasses safety controls.
      </Phase5Banner>
      <Phase5TabBar tabs={TABS} value={tab} onChange={setTab} />

      <div className="mb-4 grid gap-3 sm:grid-cols-3">
        <Phase5Stat label="Incidents" value={incidents.length} />
        <Phase5Stat
          label="Auto-resend uncertain"
          value={
            recovery.never_auto_resend_uncertain_orders === false ? "allowed" : "blocked"
          }
        />
        <Phase5Stat
          label="Reconcile first"
          value={recovery.reconcile_with_mt5_first === false ? "no" : "yes"}
        />
      </div>

      {tab === "active" &&
        (incidents.length === 0 ? (
          <Phase5Empty message="No open incidents from PRP / ITE / worker signals." />
        ) : (
          <div className="overflow-x-auto rounded-md border border-border/60">
            <table className="w-full min-w-[720px] text-left text-sm">
              <thead className="border-b border-border/60 bg-muted/20 text-xs text-muted-foreground">
                <tr>
                  <th className="px-3 py-2">ID</th>
                  <th className="px-3 py-2">Severity</th>
                  <th className="px-3 py-2">Status</th>
                  <th className="px-3 py-2">Source</th>
                  <th className="px-3 py-2">Detected</th>
                </tr>
              </thead>
              <tbody>
                {incidents.map((item, i) => {
                  const row = asRecord(item);
                  return (
                    <tr key={i} className="border-b border-border/40">
                      <td className="px-3 py-2 font-mono text-xs">
                        {str(row.incident_id)}
                      </td>
                      <td className="px-3 py-2">{str(row.severity)}</td>
                      <td className="px-3 py-2">{str(row.status)}</td>
                      <td className="px-3 py-2 text-xs text-muted-foreground">
                        {str(row.source)}
                      </td>
                      <td className="px-3 py-2 text-xs">
                        {str(row.first_detected) || "—"}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        ))}

      {tab === "recovery" && (
        <ul className="list-disc space-y-2 pl-5 text-sm text-muted-foreground">
          <li>Acknowledge → Assign → Investigate → Resolve → Escalate</li>
          <li>Retry only safe, idempotent operations</li>
          <li>Never bypass kill-switch or execution authorization on restart</li>
        </ul>
      )}

      {tab === "sources" && (
        <div className="flex flex-wrap gap-2">
          <Button size="sm" variant="secondary" asChild>
            <Link href="/incidents">ITE incidents</Link>
          </Button>
          <Button size="sm" variant="secondary" asChild>
            <Link href="/production-reliability">Production reliability</Link>
          </Button>
          <Button size="sm" variant="secondary" asChild>
            <Link href="/mission-control">Mission Control</Link>
          </Button>
        </div>
      )}
    </div>
  );
}

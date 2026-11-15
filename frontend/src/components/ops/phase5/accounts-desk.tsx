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

type Tab = "overview" | "workers" | "rules";

const TABS: { id: Tab; label: string }[] = [
  { id: "overview", label: "Overview" },
  { id: "workers", label: "Workers" },
  { id: "rules", label: "Routing rules" },
];

export function Phase5AccountsDesk() {
  const [tab, setTab] = useState<Tab>("overview");
  const q = useQuery({
    queryKey: ["p5-accounts"],
    queryFn: institutionalOpsApi.accounts,
    retry: false,
    staleTime: 10_000,
  });

  if (q.isLoading) return <Phase5Loading />;
  if (q.isError) {
    return <Phase5Error message="Account orchestration overview unavailable." />;
  }

  const data = asRecord(q.data);
  const workers = asRecord(data.workers);
  const rows = asList(workers.rows);
  const banner = str(data.banner);

  return (
    <div>
      <Phase5ModuleNav current="/account-orchestration" />
      {banner ? <Phase5Banner tone="warn">{banner}</Phase5Banner> : null}
      <Phase5Banner>
        One primary account per user. MT5 remains authoritative for trade_allowed.
        VERIFIED_LIVE display status is not trading permission. Observe-only on
        production — no duplicate workers or second VPS.
      </Phase5Banner>
      <Phase5TabBar tabs={TABS} value={tab} onChange={setTab} />

      {tab === "overview" && (
        <div className="space-y-4">
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <Phase5Stat
              label="Workers ready"
              value={Number(workers.ready_count || 0)}
            />
            <Phase5Stat
              label="Workers stale"
              value={Number(workers.stale_count || 0)}
            />
            <Phase5Stat
              label="LIVE submit"
              value={data.live_submit_allowed === true ? "allowed" : "blocked"}
            />
            <Phase5Stat
              label="Observe only"
              value={data.observe_only_production === false ? "no" : "yes"}
            />
          </div>
          <Button size="sm" variant="secondary" asChild>
            <Link href="/admin/multi-account">Admin multi-account</Link>
          </Button>
        </div>
      )}

      {tab === "workers" &&
        (rows.length === 0 ? (
          <Phase5Empty message="No worker rows reported — capacity-aware scheduling stays idle." />
        ) : (
          <ul className="divide-y divide-border/50 rounded-md border border-border/60">
            {rows.map((item, i) => {
              const row = asRecord(item);
              return (
                <li key={i} className="flex items-center justify-between px-3 py-2 text-sm">
                  <span>
                    {str(row.worker_id) || str(row.id) || `Worker ${i + 1}`}
                  </span>
                  <span className="font-mono text-xs text-muted-foreground">
                    {str(row.status) ||
                      (row.ready === true ? "ready" : "not_ready")}
                  </span>
                </li>
              );
            })}
          </ul>
        ))}

      {tab === "rules" && (
        <ul className="list-disc space-y-2 pl-5 text-sm text-muted-foreground">
          <li>Respect account ownership and authorization.</li>
          <li>Never override broker-reported permissions.</li>
          <li>Preserve existing Weltrade LIVE path and Windows MT5 host.</li>
          <li>Safe routing and capacity-aware scheduling only when workers are ready.</li>
        </ul>
      )}
    </div>
  );
}

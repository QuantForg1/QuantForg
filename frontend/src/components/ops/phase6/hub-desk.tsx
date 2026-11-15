"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { institutionalIntelligenceApi } from "@/lib/api/endpoints";
import { asList, asRecord, str } from "@/lib/desk";
import { Button } from "@/components/ui/button";
import {
  PHASE6_MODULES,
  Phase6Banner,
  Phase6Error,
  Phase6Loading,
  Phase6ModuleNav,
  Phase6Stat,
} from "./shared";

export function Phase6HubDesk() {
  const q = useQuery({
    queryKey: ["p6-hub"],
    queryFn: institutionalIntelligenceApi.summary,
    retry: false,
    staleTime: 15_000,
  });

  if (q.isLoading) return <Phase6Loading />;
  if (q.isError) {
    return <Phase6Error message="Intelligence hub unavailable." />;
  }

  const data = asRecord(q.data);
  const modules = asList(data.modules);

  return (
    <div>
      <Phase6ModuleNav current="/intelligence-center" />
      <Phase6Banner tone="ok">
        Advisory Institutional Intelligence Center. Forecasts are not guarantees.
        Approved recommendations never authorize LIVE execution. Never
        order_send / auto-rebalance / raise risk limits.
      </Phase6Banner>
      <div className="mb-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <Phase6Stat
          label="Model"
          value={str(data.model_version) || "phase6-intel-1.0.0"}
        />
        <Phase6Stat
          label="Order send"
          value={data.never_order_send === false ? "enabled" : "blocked"}
        />
        <Phase6Stat
          label="Pending recommendations"
          value={Number(data.pending_recommendations || 0)}
        />
        <Phase6Stat
          label="Auto rebalance"
          value={data.never_auto_rebalance === false ? "on" : "off"}
        />
      </div>
      <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
        {(modules.length
          ? modules
          : PHASE6_MODULES.map((m) => ({ path: m.href, label: m.label }))
        ).map((item, i) => {
          const row = asRecord(item);
          const href = str(row.path) || str(row.href) || "#";
          const label = str(row.label) || href;
          return (
            <Link
              key={i}
              href={href}
              className="rounded-md border border-border/60 bg-card/30 px-3 py-3 text-sm hover:border-accent/40"
            >
              {label}
            </Link>
          );
        })}
      </div>
      <div className="mt-4 flex flex-wrap gap-2">
        <Button size="sm" variant="secondary" asChild>
          <Link href="/ai-trading-intelligence">Phase 4 ATI</Link>
        </Button>
        <Button size="sm" variant="secondary" asChild>
          <Link href="/operations">Phase 5 Operations</Link>
        </Button>
      </div>
    </div>
  );
}

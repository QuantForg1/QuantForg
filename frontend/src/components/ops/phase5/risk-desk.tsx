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

type Tab = "enforcement" | "alerts" | "controls";

const TABS: { id: Tab; label: string }[] = [
  { id: "enforcement", label: "Enforcement" },
  { id: "alerts", label: "Alerts" },
  { id: "controls", label: "Controls" },
];

export function Phase5RiskDesk() {
  const [tab, setTab] = useState<Tab>("enforcement");
  const q = useQuery({
    queryKey: ["p5-risk"],
    queryFn: institutionalOpsApi.risk,
    retry: false,
    staleTime: 10_000,
  });

  if (q.isLoading) return <Phase5Loading />;
  if (q.isError) {
    return <Phase5Error message="Risk automation overview unavailable." />;
  }

  const data = asRecord(q.data);
  const enforcement = asRecord(data.enforcement);
  const actions = asList(enforcement.actions);
  const alerts = asList(data.ati_alerts);

  return (
    <div>
      <Phase5ModuleNav current="/risk-automation" />
      <Phase5Banner tone="warn">
        Backend risk enforcement remains authoritative. This desk never raises
        limits, never lets AI override hard constraints, and never invents
        balances or margin. Trader prefs stay on Risk Center.
      </Phase5Banner>
      <Phase5TabBar tabs={TABS} value={tab} onChange={setTab} />

      {tab === "enforcement" && (
        <div className="space-y-4">
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            <Phase5Stat
              label="Backend authoritative"
              value={enforcement.backend_authoritative === false ? "no" : "yes"}
            />
            <Phase5Stat
              label="UI can raise limits"
              value={enforcement.ui_cannot_raise_limits === false ? "yes" : "no"}
            />
            <Phase5Stat
              label="ATI advisory"
              value={data.ati_advisory_only === false ? "no" : "yes"}
            />
          </div>
          <ul className="grid gap-2 sm:grid-cols-2">
            {actions.map((a, i) => (
              <li
                key={i}
                className="rounded-md border border-border/60 bg-card/30 px-3 py-2 text-sm"
              >
                {str(a) || String(a)}
              </li>
            ))}
          </ul>
        </div>
      )}

      {tab === "alerts" &&
        (alerts.length === 0 ? (
          <Phase5Empty message="No AI risk alerts from supplied facts (advisory empty state)." />
        ) : (
          <ul className="divide-y divide-border/50 rounded-md border border-border/60">
            {alerts.map((item, i) => {
              const row = asRecord(item);
              return (
                <li key={i} className="px-3 py-2 text-sm">
                  <div className="font-medium">
                    {str(row.title) || str(row.code) || `Alert ${i + 1}`}
                  </div>
                  <div className="text-xs text-muted-foreground">
                    {str(row.severity)} — {str(row.explanation)}
                  </div>
                </li>
              );
            })}
          </ul>
        ))}

      {tab === "controls" && (
        <div className="flex flex-wrap gap-2">
          <Button size="sm" variant="secondary" asChild>
            <Link href="/risk-center">Trader Risk Center</Link>
          </Button>
          <Button size="sm" variant="secondary" asChild>
            <Link href="/admin/live-trading">Kill / LIVE panel</Link>
          </Button>
          <Button size="sm" variant="secondary" asChild>
            <Link href="/ai-trading-intelligence">ATI alerts</Link>
          </Button>
        </div>
      )}
    </div>
  );
}

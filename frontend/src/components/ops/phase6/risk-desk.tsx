"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { institutionalIntelligenceApi } from "@/lib/api/endpoints";
import { asList, asRecord, str } from "@/lib/desk";
import { Button } from "@/components/ui/button";
import {
  Phase6Banner,
  Phase6Empty,
  Phase6Error,
  Phase6Loading,
  Phase6ModuleNav,
  Phase6Stat,
} from "./shared";

export function Phase6RiskDesk() {
  const q = useQuery({
    queryKey: ["p6-risk"],
    queryFn: institutionalIntelligenceApi.risk,
    retry: false,
    staleTime: 15_000,
  });

  if (q.isLoading) return <Phase6Loading />;
  if (q.isError) {
    return <Phase6Error message="Predictive risk overview unavailable." />;
  }

  const data = asRecord(q.data);
  const enforcement = asRecord(data.enforcement);
  const alerts = asList(data.ati_alerts);

  return (
    <div>
      <Phase6ModuleNav current="/predictive-risk" />
      <Phase6Banner tone="warn">
        Hard risk limits always take priority. Predictive AI never overrides
        constraints or raises limits. Backend enforcement remains authoritative.
      </Phase6Banner>
      <div className="mb-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <Phase6Stat
          label="Hard limits priority"
          value={enforcement.hard_limits_priority === false ? "no" : "yes"}
        />
        <Phase6Stat
          label="AI can override"
          value={
            enforcement.ai_cannot_override_hard_constraints === false
              ? "yes"
              : "no"
          }
        />
        <Phase6Stat
          label="UI can raise limits"
          value={enforcement.ui_cannot_raise_limits === false ? "yes" : "no"}
        />
        <Phase6Stat
          label="ATI advisory"
          value={data.ati_advisory_only === false ? "no" : "yes"}
        />
      </div>
      {alerts.length === 0 ? (
        <Phase6Empty message="No ATI risk alerts from supplied empty facts (honest empty)." />
      ) : (
        <ul className="mb-4 divide-y divide-border/50 rounded-md border border-border/60">
          {alerts.map((item, i) => {
            const row = asRecord(item);
            return (
              <li key={i} className="px-3 py-2 text-sm">
                <div className="font-medium">
                  {str(row.title) || str(row.code)}
                </div>
                <div className="text-xs text-muted-foreground">
                  {str(row.severity)} — {str(row.explanation)}
                </div>
              </li>
            );
          })}
        </ul>
      )}
      <div className="flex flex-wrap gap-2">
        <Button size="sm" variant="secondary" asChild>
          <Link href="/robot-control-center">Robot &amp; Risk</Link>
        </Button>
        <Button size="sm" variant="secondary" asChild>
          <Link href="/institutional-risk-analytics">IRAP</Link>
        </Button>
        <Button size="sm" variant="secondary" asChild>
          <Link href="/risk-automation">Phase 5 risk</Link>
        </Button>
      </div>
    </div>
  );
}

"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import {
  executionIntelligenceApi,
  institutionalOpsApi,
} from "@/lib/api/endpoints";
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

type Tab = "metrics" | "lifecycle" | "analytics";

const TABS: { id: Tab; label: string }[] = [
  { id: "metrics", label: "Metrics" },
  { id: "lifecycle", label: "Lifecycle" },
  { id: "analytics", label: "Analytics" },
];

function fmtPct(v: unknown): string {
  if (typeof v !== "number" || Number.isNaN(v)) return "—";
  return `${(v * 100).toFixed(1)}%`;
}

function fmtNum(v: unknown, digits = 1): string {
  if (typeof v !== "number" || Number.isNaN(v)) return "—";
  return v.toFixed(digits);
}

export function Phase5ExecutionDesk() {
  const [tab, setTab] = useState<Tab>("metrics");
  const overviewQ = useQuery({
    queryKey: ["p5-exec"],
    queryFn: institutionalOpsApi.execution,
    retry: false,
    staleTime: 10_000,
  });
  const analyticsQ = useQuery({
    queryKey: ["p5-exec-analytics"],
    queryFn: executionIntelligenceApi.analytics,
    retry: false,
    enabled: tab === "analytics",
    staleTime: 15_000,
  });

  if (overviewQ.isLoading) return <Phase5Loading />;
  if (overviewQ.isError) {
    return <Phase5Error message="Execution intelligence overview unavailable." />;
  }

  const data = asRecord(overviewQ.data);
  const metrics = asRecord(data.metrics);
  const stages = asList(data.lifecycle_stages);
  const empty = data.empty === true || Number(metrics.attempt_count || 0) === 0;

  return (
    <div>
      <Phase5ModuleNav current="/execution-intelligence" />
      <Phase5Banner>
        Metrics use persisted execution attempts only. Signal generation is never
        counted as successful broker execution. OMS and Trading Core behavior is
        preserved.
      </Phase5Banner>
      <Phase5TabBar tabs={TABS} value={tab} onChange={setTab} />

      {tab === "metrics" && (
        <div className="space-y-4">
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <Phase5Stat label="Attempts" value={Number(metrics.attempt_count || 0)} />
            <Phase5Stat label="Success rate" value={fmtPct(metrics.success_rate)} />
            <Phase5Stat
              label="Avg latency (ms)"
              value={fmtNum(metrics.avg_latency_ms, 0)}
            />
            <Phase5Stat label="Rejection rate" value={fmtPct(metrics.rejection_rate)} />
            <Phase5Stat label="Avg slippage" value={fmtNum(metrics.avg_slippage, 2)} />
            <Phase5Stat label="Decisions" value={Number(metrics.decision_count || 0)} />
            <Phase5Stat
              label="Fabricated"
              value={metrics.fabricated === true ? "yes" : "no"}
            />
            <Phase5Stat label="Source" value={str(metrics.source) || "—"} />
          </div>
          {empty ? (
            <Phase5Empty message="No persisted execution attempts yet — metrics stay empty rather than invented." />
          ) : null}
          <div className="flex flex-wrap gap-2">
            <Button size="sm" variant="secondary" asChild>
              <Link href="/order-monitor">Order monitor</Link>
            </Button>
            <Button size="sm" variant="secondary" asChild>
              <Link href="/dashboard">Dashboard</Link>
            </Button>
          </div>
        </div>
      )}

      {tab === "lifecycle" && (
        <ol className="grid gap-2 sm:grid-cols-2 lg:grid-cols-5">
          {stages.map((stage, i) => (
            <li
              key={i}
              className="rounded-md border border-border/60 bg-card/30 px-3 py-2 text-sm capitalize"
            >
              <span className="mr-2 font-mono text-xs text-muted-foreground">
                {i + 1}.
              </span>
              {str(stage) || String(stage)}
            </li>
          ))}
        </ol>
      )}

      {tab === "analytics" &&
        (analyticsQ.isLoading ? (
          <Phase5Loading />
        ) : analyticsQ.isError ? (
          <Phase5Empty message="Analytics endpoint returned no data for this session." />
        ) : (
          <pre className="overflow-auto rounded-md border border-border/60 bg-muted/10 p-3 text-xs">
            {JSON.stringify(analyticsQ.data, null, 2)}
          </pre>
        ))}
    </div>
  );
}

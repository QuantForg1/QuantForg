"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { institutionalIntelligenceApi } from "@/lib/api/endpoints";
import { asRecord, str } from "@/lib/desk";
import { Button } from "@/components/ui/button";
import {
  Phase6Banner,
  Phase6Empty,
  Phase6Error,
  Phase6Loading,
  Phase6ModuleNav,
  Phase6Stat,
} from "./shared";

function fmtPct(v: unknown): string {
  if (typeof v !== "number" || Number.isNaN(v)) return "—";
  return `${(v * 100).toFixed(1)}%`;
}

function fmtNum(v: unknown, digits = 1): string {
  if (typeof v !== "number" || Number.isNaN(v)) return "—";
  return v.toFixed(digits);
}

export function Phase6ExecutionDesk() {
  const q = useQuery({
    queryKey: ["p6-execution"],
    queryFn: institutionalIntelligenceApi.execution,
    retry: false,
    staleTime: 10_000,
  });

  if (q.isLoading) return <Phase6Loading />;
  if (q.isError) {
    return <Phase6Error message="Execution optimization overview unavailable." />;
  }

  const data = asRecord(q.data);
  const metrics = asRecord(data.metrics);
  const rules = asRecord(data.rules);
  const empty = data.empty === true || Number(metrics.attempt_count || 0) === 0;

  return (
    <div>
      <Phase6ModuleNav current="/execution-optimization" />
      <Phase6Banner>
        Only persisted execution attempts. Signals and dispatches are never
        counted as fills without broker/MT5 confirmation. Routing is never
        changed automatically.
      </Phase6Banner>
      <div className="mb-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <Phase6Stat label="Attempts" value={Number(metrics.attempt_count || 0)} />
        <Phase6Stat label="Success rate" value={fmtPct(metrics.success_rate)} />
        <Phase6Stat
          label="Avg latency (ms)"
          value={fmtNum(metrics.avg_latency_ms, 0)}
        />
        <Phase6Stat label="Rejection rate" value={fmtPct(metrics.rejection_rate)} />
        <Phase6Stat label="Avg slippage" value={fmtNum(metrics.avg_slippage, 2)} />
        <Phase6Stat
          label="Fabricated"
          value={metrics.fabricated === true ? "yes" : "no"}
        />
        <Phase6Stat
          label="Signals are fills"
          value={rules.signals_are_not_fills === false ? "yes" : "no"}
        />
        <Phase6Stat label="Source" value={str(metrics.source) || "—"} />
      </div>
      {empty ? (
        <Phase6Empty message="No persisted execution attempts — metrics stay empty." />
      ) : null}
      <div className="flex flex-wrap gap-2">
        <Button size="sm" variant="secondary" asChild>
          <Link href="/execution-intelligence">Execution intelligence</Link>
        </Button>
        <Button size="sm" variant="secondary" asChild>
          <Link href="/execution-quality-suite">EQS</Link>
        </Button>
      </div>
    </div>
  );
}

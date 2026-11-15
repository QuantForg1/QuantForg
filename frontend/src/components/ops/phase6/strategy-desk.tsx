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

export function Phase6StrategyDesk() {
  const q = useQuery({
    queryKey: ["p6-strategy"],
    queryFn: institutionalIntelligenceApi.strategy,
    retry: false,
    staleTime: 15_000,
  });

  if (q.isLoading) return <Phase6Loading />;
  if (q.isError) {
    return <Phase6Error message="Strategy analytics overview unavailable." />;
  }

  const data = asRecord(q.data);
  const strategies = asList(data.strategies);

  return (
    <div>
      <Phase6ModuleNav current="/strategy-analytics" />
      <Phase6Banner>
        Metrics are shown only when present. Backtest, paper, and live results
        are never mixed. Missing metrics stay empty rather than invented.
      </Phase6Banner>
      <div className="mb-4 grid gap-3 sm:grid-cols-3">
        <Phase6Stat label="Strategies" value={strategies.length} />
        <Phase6Stat
          label="Empty"
          value={data.empty === true ? "yes" : "no"}
        />
        <Phase6Stat label="Model" value={str(data.model_version)} />
      </div>
      {strategies.length === 0 ? (
        <Phase6Empty message="No strategy analytics rows available in this environment." />
      ) : (
        <div className="overflow-x-auto rounded-md border border-border/60">
          <table className="w-full min-w-[640px] text-left text-sm">
            <thead className="border-b border-border/60 bg-muted/20 text-xs text-muted-foreground">
              <tr>
                <th className="px-3 py-2">Strategy</th>
                <th className="px-3 py-2">Class</th>
                <th className="px-3 py-2">Version</th>
                <th className="px-3 py-2">Metrics keys</th>
              </tr>
            </thead>
            <tbody>
              {strategies.map((item, i) => {
                const row = asRecord(item);
                const metrics = asRecord(row.metrics);
                return (
                  <tr key={i} className="border-b border-border/40">
                    <td className="px-3 py-2">
                      {str(row.name) || str(row.strategy_id) || `S${i + 1}`}
                    </td>
                    <td className="px-3 py-2 font-mono text-xs">
                      {str(row.result_class)}
                    </td>
                    <td className="px-3 py-2 text-xs">{str(row.version) || "—"}</td>
                    <td className="px-3 py-2 text-xs text-muted-foreground">
                      {Object.keys(metrics).join(", ") || "none"}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
      <div className="mt-4 flex flex-wrap gap-2">
        <Button size="sm" variant="secondary" asChild>
          <Link href="/strategy-intelligence-center">SIC desk</Link>
        </Button>
        <Button size="sm" variant="secondary" asChild>
          <Link href="/performance-intelligence">Performance intel</Link>
        </Button>
      </div>
    </div>
  );
}

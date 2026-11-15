"use client";

import { useQuery } from "@tanstack/react-query";
import { quantitativeResearchControlApi } from "@/lib/api/endpoints";
import { asList, asRecord, str } from "@/lib/desk";
import {
  Phase8Banner,
  Phase8Empty,
  Phase8Error,
  Phase8Loading,
  Phase8ModuleNav,
  Phase8Stat,
} from "./shared";

export function Phase8LeaderboardDesk() {
  const q = useQuery({
    queryKey: ["p8-lb"],
    queryFn: quantitativeResearchControlApi.leaderboard,
    retry: false,
  });
  if (q.isLoading) return <Phase8Loading />;
  if (q.isError) return <Phase8Error message="Leaderboard unavailable." />;
  const data = asRecord(q.data);
  const rows = asList(data.rows);

  return (
    <div>
      <Phase8ModuleNav current="/research-leaderboard" />
      <Phase8Banner tone="ok">
        Ranked by risk-adjusted then sample size — never profit alone.
        Validation classes distinguish research / OOS / approved / monitored.
      </Phase8Banner>
      <div className="mb-4 grid gap-3 sm:grid-cols-3">
        <Phase8Stat label="Rows" value={Number(data.count || 0)} />
        <Phase8Stat label="Ranking" value={str(data.ranking)} />
        <Phase8Stat
          label="Profit-only"
          value={data.never_profit_only === false ? "yes" : "no"}
        />
      </div>
      {rows.length === 0 ? (
        <Phase8Empty message="No comparable strategies available." />
      ) : (
        <div className="space-y-2">
          {rows.map((item, i) => {
            const row = asRecord(item);
            return (
              <div
                key={i}
                className="rounded-md border border-border/60 px-3 py-2 font-mono text-xs"
              >
                {str(row.validation_class)} · {str(row.name) || str(row.strategy_id)}{" "}
                · sharpe={str(row.risk_adjusted) || "—"} · n=
                {str(row.sample_size) || "—"}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

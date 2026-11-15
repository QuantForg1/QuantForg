"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { institutionalIntelligenceApi } from "@/lib/api/endpoints";
import { asList, asRecord, str } from "@/lib/desk";
import {
  Phase6Banner,
  Phase6Empty,
  Phase6Error,
  Phase6Loading,
  Phase6ModuleNav,
  Phase6Stat,
} from "./shared";

export function Phase6ReportsDesk() {
  const q = useQuery({
    queryKey: ["p6-reports"],
    queryFn: institutionalIntelligenceApi.reports,
    retry: false,
    staleTime: 15_000,
  });

  if (q.isLoading) return <Phase6Loading />;
  if (q.isError) {
    return <Phase6Error message="Institutional reports overview unavailable." />;
  }

  const data = asRecord(q.data);
  const catalogs = asList(data.catalogs);
  const rules = asRecord(data.rules);

  return (
    <div>
      <Phase6ModuleNav current="/institutional-reports" />
      <Phase6Banner>
        Reports distinguish actual, backtested and simulated results. Incomplete
        catalogs are labeled — never presented as complete.
      </Phase6Banner>
      <div className="mb-4 grid gap-3 sm:grid-cols-3">
        <Phase6Stat label="Catalogs" value={catalogs.length} />
        <Phase6Stat
          label="Incomplete as complete"
          value={
            rules.never_present_incomplete_as_complete === false ? "allowed" : "blocked"
          }
        />
        <Phase6Stat label="Model" value={str(data.model_version)} />
      </div>
      {catalogs.length === 0 ? (
        <Phase6Empty message="No report catalogs composed." />
      ) : (
        <div className="grid gap-2 sm:grid-cols-2">
          {catalogs.map((item, i) => {
            const row = asRecord(item);
            const href = str(row.path) || "#";
            return (
              <Link
                key={i}
                href={href}
                className="rounded-md border border-border/60 bg-card/30 px-3 py-3 text-sm hover:border-accent/40"
              >
                <div className="font-medium">{str(row.label) || href}</div>
                <div className="text-xs text-muted-foreground">
                  class: {str(row.result_class) || "unknown"}
                </div>
              </Link>
            );
          })}
        </div>
      )}
    </div>
  );
}

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

type Tab = "registry" | "stages" | "approvals" | "rules";

const TABS: { id: Tab; label: string }[] = [
  { id: "registry", label: "Registry" },
  { id: "stages", label: "Stages" },
  { id: "approvals", label: "Approvals" },
  { id: "rules", label: "LIVE gates" },
];

export function Phase5LifecycleDesk() {
  const [tab, setTab] = useState<Tab>("registry");
  const q = useQuery({
    queryKey: ["p5-lifecycle"],
    queryFn: institutionalOpsApi.strategyLifecycle,
    retry: false,
    staleTime: 15_000,
  });

  if (q.isLoading) return <Phase5Loading />;
  if (q.isError) {
    return <Phase5Error message="Strategy lifecycle overview unavailable." />;
  }

  const data = asRecord(q.data);
  const strategies = asList(data.strategies);
  const stages = asList(data.stages).map((s) => str(s) || String(s));
  const irdp = asRecord(data.irdp);
  const approvals = asList(irdp.pending_approvals);
  const liveAllowed = strategies.filter(
    (s) => asRecord(s).live_deploy_allowed === true,
  ).length;

  return (
    <div>
      <Phase5ModuleNav current="/strategy-lifecycle" />
      <Phase5Banner tone="warn">
        Backtest pass is not LIVE. AI recommendations remain advisory until
        separately reviewed. LIVE deployment requires human approval, risk
        clearance, and owner authorization — governance state only on this desk.
      </Phase5Banner>
      <Phase5TabBar tabs={TABS} value={tab} onChange={setTab} />

      <div className="mb-4 grid gap-3 sm:grid-cols-4">
        <Phase5Stat label="Strategies" value={strategies.length} />
        <Phase5Stat label="Stages" value={stages.length || 10} />
        <Phase5Stat label="Pending approvals" value={approvals.length} />
        <Phase5Stat
          label="LIVE deploy eligible"
          value={liveAllowed}
          hint="Explicit gates only"
        />
      </div>

      {tab === "registry" &&
        (strategies.length === 0 ? (
          <Phase5Empty message="No strategies in the governance registry." />
        ) : (
          <div className="overflow-x-auto rounded-md border border-border/60">
            <table className="w-full min-w-[640px] text-left text-sm">
              <thead className="border-b border-border/60 bg-muted/20 text-xs text-muted-foreground">
                <tr>
                  <th className="px-3 py-2">Strategy</th>
                  <th className="px-3 py-2">Phase 5 stage</th>
                  <th className="px-3 py-2">ISLM</th>
                  <th className="px-3 py-2">LIVE eligible</th>
                </tr>
              </thead>
              <tbody>
                {strategies.map((item, i) => {
                  const row = asRecord(item);
                  return (
                    <tr key={i} className="border-b border-border/40">
                      <td className="px-3 py-2 font-medium">
                        {str(row.name) || str(row.strategy_id) || `Strategy ${i + 1}`}
                      </td>
                      <td className="px-3 py-2 font-mono text-xs">
                        {str(row.phase5_stage)}
                      </td>
                      <td className="px-3 py-2 text-xs text-muted-foreground">
                        {str(row.islm_stage)}
                      </td>
                      <td className="px-3 py-2 text-xs">
                        {row.live_deploy_allowed === true ? "yes" : "no"}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        ))}

      {tab === "stages" && (
        <ol className="grid gap-2 sm:grid-cols-2 lg:grid-cols-5">
          {(stages.length
            ? stages
            : [
                "Draft",
                "Backtesting",
                "Validation",
                "Risk Review",
                "Approval",
                "Deployment",
                "Monitoring",
                "Paused",
                "Rollback",
                "Archived",
              ]
          ).map((stage, i) => (
            <li
              key={stage}
              className="rounded-md border border-border/60 bg-card/30 px-3 py-2 text-sm"
            >
              <span className="mr-2 font-mono text-xs text-muted-foreground">
                {i + 1}.
              </span>
              {stage}
            </li>
          ))}
        </ol>
      )}

      {tab === "approvals" &&
        (approvals.length === 0 ? (
          <Phase5Empty message="No pending IRDP approvals." />
        ) : (
          <ul className="divide-y divide-border/50 rounded-md border border-border/60">
            {approvals.map((item, i) => {
              const row = asRecord(item);
              return (
                <li key={i} className="px-3 py-2 text-sm">
                  {str(row.id) || str(row.release_id) || `Approval ${i + 1}`} —{" "}
                  {str(row.status) || "pending"}
                </li>
              );
            })}
          </ul>
        ))}

      {tab === "rules" && (
        <div className="space-y-3 text-sm text-muted-foreground">
          <p>Deployment into broker LIVE is never implied by simulation success.</p>
          <div className="flex flex-wrap gap-2">
            <Button size="sm" variant="secondary" asChild>
              <Link href="/institutional-strategy-lifecycle">ISLM desk</Link>
            </Button>
            <Button size="sm" variant="secondary" asChild>
              <Link href="/institutional-release">IRDP desk</Link>
            </Button>
            <Button size="sm" variant="secondary" asChild>
              <Link href="/quantforg-strategy-factory/approvals">QSF approvals</Link>
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}

"use client";

import { useQuery } from "@tanstack/react-query";
import { quantitativeResearchControlApi } from "@/lib/api/endpoints";
import { asList, asRecord } from "@/lib/desk";
import {
  Phase8Banner,
  Phase8Empty,
  Phase8Error,
  Phase8Loading,
  Phase8ModuleNav,
  Phase8Stat,
} from "./shared";

export function Phase8OptimizeDesk() {
  const opt = useQuery({
    queryKey: ["p8-opt"],
    queryFn: quantitativeResearchControlApi.optimizationOverview,
    retry: false,
  });
  const rob = useQuery({
    queryKey: ["p8-rob"],
    queryFn: quantitativeResearchControlApi.robustnessOverview,
    retry: false,
  });
  if (opt.isLoading) return <Phase8Loading />;
  if (opt.isError) return <Phase8Error message="Optimization unavailable." />;
  const o = asRecord(opt.data);
  const r = asRecord(rob.data);
  const findings = asList(r.findings);

  return (
    <div>
      <Phase8ModuleNav current="/strategy-optimization" />
      <Phase8Banner tone="warn">
        Optimize on training data only. Holdout reserved. Optimized parameters
        never auto-deploy to LIVE. Robustness findings require evidence —
        no statistical claims without assumptions.
      </Phase8Banner>
      <div className="mb-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <Phase8Stat
          label="Auto deploy"
          value={
            asRecord(o.rules).never_auto_deploy_optimized_params === false
              ? "allowed"
              : "blocked"
          }
        />
        <Phase8Stat
          label="Holdout reserved"
          value={asRecord(o.rules).holdout_reserved === false ? "no" : "yes"}
        />
        <Phase8Stat
          label="Opt=LIVE"
          value={o.optimization_is_not_live === false ? "yes" : "no"}
        />
        <Phase8Stat label="Robustness findings" value={findings.length} />
      </div>
      {findings.length === 0 ? (
        <Phase8Empty message="No robustness findings available yet." />
      ) : null}
    </div>
  );
}

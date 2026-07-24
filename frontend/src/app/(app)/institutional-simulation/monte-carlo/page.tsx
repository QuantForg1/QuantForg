"use client";

import { PageHeader } from "@/components/layout/page-header";
import { PageMotion } from "@/components/desk/motion";
import { IseMonteCarloWorkspace } from "@/components/ops/ise-workspaces";

export default function IseMonteCarloPage() {
  return (
    <div>
      <PageHeader
        title="Monte Carlo"
        description="100–5000 paths — probability of ruin, confidence intervals, cases."
      />
      <PageMotion>
        <IseMonteCarloWorkspace />
      </PageMotion>
    </div>
  );
}

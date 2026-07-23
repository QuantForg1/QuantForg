"use client";

import { PageHeader } from "@/components/layout/page-header";
import { PageMotion } from "@/components/desk/motion";
import { EqsDashboardWorkspace } from "@/components/ops/eqs-workspaces";

export default function ExecutionQualitySuitePage() {
  return (
    <div>
      <PageHeader
        title="Execution Quality Suite"
        description="Execution intelligence from signal to broker — latency, slippage, fills. Never modifies production."
      />
      <PageMotion>
        <EqsDashboardWorkspace />
      </PageMotion>
    </div>
  );
}

"use client";

import { PageHeader } from "@/components/layout/page-header";
import { PageMotion } from "@/components/desk/motion";
import { EqsReportsWorkspace } from "@/components/ops/eqs-workspaces";

export default function EqsReportsPage() {
  return (
    <div>
      <PageHeader
        title="Execution Reports"
        description="Daily, weekly, monthly quality, latency, slippage, and broker reports."
      />
      <PageMotion>
        <EqsReportsWorkspace />
      </PageMotion>
    </div>
  );
}

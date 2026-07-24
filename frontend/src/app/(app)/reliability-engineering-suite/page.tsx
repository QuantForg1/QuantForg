"use client";

import { PageHeader } from "@/components/layout/page-header";
import { PageMotion } from "@/components/desk/motion";
import { ResDashboardWorkspace } from "@/components/ops/res-workspaces";

export default function ReliabilityEngineeringSuitePage() {
  return (
    <div>
      <PageHeader
        title="Reliability Engineering Suite"
        description="Platform health, availability, recovery and failure analytics. Never modifies production."
      />
      <PageMotion>
        <ResDashboardWorkspace />
      </PageMotion>
    </div>
  );
}

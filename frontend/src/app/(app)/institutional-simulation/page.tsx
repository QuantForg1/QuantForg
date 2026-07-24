"use client";

import { PageHeader } from "@/components/layout/page-header";
import { PageMotion } from "@/components/desk/motion";
import { IseDashboardWorkspace } from "@/components/ops/ise-workspaces";

export default function InstitutionalSimulationPage() {
  return (
    <div>
      <PageHeader
        title="Institutional Simulation Engine"
        description="Digital twin of QuantForg — historical replay, stress, Monte Carlo. Never modifies production."
      />
      <PageMotion>
        <IseDashboardWorkspace />
      </PageMotion>
    </div>
  );
}

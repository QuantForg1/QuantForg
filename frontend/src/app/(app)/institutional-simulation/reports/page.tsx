"use client";

import { PageHeader } from "@/components/layout/page-header";
import { PageMotion } from "@/components/desk/motion";
import { IseReportsWorkspace } from "@/components/ops/ise-workspaces";

export default function IseReportsPage() {
  return (
    <div>
      <PageHeader
        title="Simulation Reports"
        description="Simulation, scenario comparison, stress, walk-forward, Monte Carlo reports."
      />
      <PageMotion>
        <IseReportsWorkspace />
      </PageMotion>
    </div>
  );
}

"use client";

import { PageHeader } from "@/components/layout/page-header";
import { PageMotion } from "@/components/desk/motion";
import { IrlDashboardWorkspace } from "@/components/ops/irl-workspaces";

export default function InstitutionalResearchLabPage() {
  return (
    <div>
      <PageHeader
        title="Institutional Research Lab"
        description="Isolated research workspace — design, replay, benchmark, and statistically validate candidate ideas. Never executes live trades or writes production tables."
      />
      <PageMotion>
        <IrlDashboardWorkspace />
      </PageMotion>
    </div>
  );
}

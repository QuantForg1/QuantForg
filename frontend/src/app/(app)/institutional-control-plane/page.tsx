"use client";

import { PageHeader } from "@/components/layout/page-header";
import { PageMotion } from "@/components/desk/motion";
import { IcpDashboardWorkspace } from "@/components/ops/icp-workspaces";

export default function InstitutionalControlPlanePage() {
  return (
    <div>
      <PageHeader
        title="Control Plane"
        description="ICP — executive operations view across the QuantForg platform. Never modifies production."
      />
      <PageMotion>
        <IcpDashboardWorkspace />
      </PageMotion>
    </div>
  );
}

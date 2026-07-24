"use client";

import { PageHeader } from "@/components/layout/page-header";
import { PageMotion } from "@/components/desk/motion";
import { IrdpDashboardWorkspace } from "@/components/ops/irdp-workspaces";

export default function InstitutionalReleasePage() {
  return (
    <div>
      <PageHeader
        title="Institutional Release Platform"
        description="Release governance with human approval — never auto-approves or executes trades."
      />
      <PageMotion>
        <IrdpDashboardWorkspace />
      </PageMotion>
    </div>
  );
}

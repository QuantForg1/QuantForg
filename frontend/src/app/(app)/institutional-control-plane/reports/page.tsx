"use client";

import { PageHeader } from "@/components/layout/page-header";
import { PageMotion } from "@/components/desk/motion";
import { IcpReportsWorkspace } from "@/components/ops/icp-workspaces";

export default function IcpReportsPage() {
  return (
    <div>
      <PageHeader
        title="Executive Reports"
        description="Daily brief, weekly ops, monthly platform and quarterly executive reports."
      />
      <PageMotion>
        <IcpReportsWorkspace />
      </PageMotion>
    </div>
  );
}

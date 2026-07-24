"use client";

import { PageHeader } from "@/components/layout/page-header";
import { PageMotion } from "@/components/desk/motion";
import { IrdpApprovalsWorkspace } from "@/components/ops/irdp-workspaces";

export default function IrdpApprovalsPage() {
  return (
    <div>
      <PageHeader
        title="Approval Workspace"
        description="Explicit human approve/reject decisions. IRDP never auto-approves."
      />
      <PageMotion>
        <IrdpApprovalsWorkspace />
      </PageMotion>
    </div>
  );
}

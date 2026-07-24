"use client";

import { PageHeader } from "@/components/layout/page-header";
import { PageMotion } from "@/components/desk/motion";
import { QsfWorkspacePanel } from "@/components/ops/qsf-workspaces";

export default function QsfWorkspacePage() {
  return (
    <div>
      <PageHeader
        title="Strategy Workspace"
        description="QSF work items — owner, evidence, dependencies, approvals."
      />
      <PageMotion>
        <QsfWorkspacePanel />
      </PageMotion>
    </div>
  );
}

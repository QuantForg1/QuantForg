"use client";

import { PageHeader } from "@/components/layout/page-header";
import { PageMotion } from "@/components/desk/motion";
import { QpmAllocationWorkspace } from "@/components/ops/qpm-workspaces";

export default function QpmAllocationPage() {
  return (
    <div>
      <PageHeader
        title="Allocation Explorer"
        description="Recommended weights — advisory only. Human approval required."
      />
      <PageMotion>
        <QpmAllocationWorkspace />
      </PageMotion>
    </div>
  );
}

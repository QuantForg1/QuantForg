"use client";

import { PageHeader } from "@/components/layout/page-header";
import { PageMotion } from "@/components/desk/motion";
import { IslmReportsWorkspace } from "@/components/ops/islm-workspaces";

export default function IslmReportsPage() {
  return (
    <div>
      <PageHeader
        title="Lifecycle Reports"
        description="Timeline, version, lifecycle, health and evidence reports — read-only."
      />
      <PageMotion>
        <IslmReportsWorkspace />
      </PageMotion>
    </div>
  );
}

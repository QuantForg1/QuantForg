"use client";

import { PageHeader } from "@/components/layout/page-header";
import { PageMotion } from "@/components/desk/motion";
import { IrdpReportsWorkspace } from "@/components/ops/irdp-workspaces";

export default function IrdpReportsPage() {
  return (
    <div>
      <PageHeader
        title="Release Reports"
        description="Release, timeline, approval history, rollback, and health reports."
      />
      <PageMotion>
        <IrdpReportsWorkspace />
      </PageMotion>
    </div>
  );
}

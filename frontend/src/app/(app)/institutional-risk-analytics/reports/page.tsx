"use client";

import { PageHeader } from "@/components/layout/page-header";
import { PageMotion } from "@/components/desk/motion";
import { IrapReportsWorkspace } from "@/components/ops/irap-workspaces";

export default function IrapReportsPage() {
  return (
    <div>
      <PageHeader
        title="Risk Reports"
        description="Daily, weekly, monthly, quarterly portfolio and stress risk reports."
      />
      <PageMotion>
        <IrapReportsWorkspace />
      </PageMotion>
    </div>
  );
}

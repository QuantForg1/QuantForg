"use client";

import { PageHeader } from "@/components/layout/page-header";
import { PageMotion } from "@/components/desk/motion";
import { AqcReportsWorkspace } from "@/components/ops/aqc-workspaces";

export default function AqcReportsPage() {
  return (
    <div>
      <PageHeader
        title="Executive Reports"
        description="Daily, weekly, and monthly operational summaries — advisory only."
      />
      <PageMotion>
        <AqcReportsWorkspace />
      </PageMotion>
    </div>
  );
}

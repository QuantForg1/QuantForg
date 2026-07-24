"use client";

import { PageHeader } from "@/components/layout/page-header";
import { PageMotion } from "@/components/desk/motion";
import { ResReportsWorkspace } from "@/components/ops/res-workspaces";

export default function ResReportsPage() {
  return (
    <div>
      <PageHeader
        title="Reliability Reports"
        description="Daily, weekly, monthly reliability reports and incident summaries."
      />
      <PageMotion>
        <ResReportsWorkspace />
      </PageMotion>
    </div>
  );
}

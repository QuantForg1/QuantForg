"use client";

import { PageHeader } from "@/components/layout/page-header";
import { PageMotion } from "@/components/desk/motion";
import { IrlReportsWorkspace } from "@/components/ops/irl-workspaces";

export default function IrlReportsPage() {
  return (
    <div>
      <PageHeader
        title="IRL Reports"
        description="Research replay reports with statistics, significance, and Research Passed / Failed verdicts."
      />
      <PageMotion>
        <IrlReportsWorkspace />
      </PageMotion>
    </div>
  );
}

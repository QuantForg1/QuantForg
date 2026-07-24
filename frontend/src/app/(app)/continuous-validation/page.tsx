"use client";

import { PageHeader } from "@/components/layout/page-header";
import { PageMotion } from "@/components/desk/motion";
import { CvfDashboardWorkspace } from "@/components/ops/cvf-workspaces";

export default function ContinuousValidationPage() {
  return (
    <div>
      <PageHeader
        title="Continuous Validation"
        description="Replay vs live consistency, drift, and evidence. Never modifies production."
      />
      <PageMotion>
        <CvfDashboardWorkspace />
      </PageMotion>
    </div>
  );
}

"use client";

import { PageHeader } from "@/components/layout/page-header";
import { PageMotion } from "@/components/desk/motion";
import { IepComparisonWorkspace } from "@/components/ops/iep-workspaces";

export default function IepComparisonPage() {
  return (
    <div>
      <PageHeader
        title="Comparison Workspace"
        description="Baseline vs variants ranked by evidence — advisory only."
      />
      <PageMotion>
        <IepComparisonWorkspace />
      </PageMotion>
    </div>
  );
}

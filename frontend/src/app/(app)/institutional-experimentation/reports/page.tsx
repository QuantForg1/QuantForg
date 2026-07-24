"use client";

import { PageHeader } from "@/components/layout/page-header";
import { PageMotion } from "@/components/desk/motion";
import { IepReportsWorkspace } from "@/components/ops/iep-workspaces";

export default function IepReportsPage() {
  return (
    <div>
      <PageHeader
        title="Experiment Reports"
        description="Experiment, comparison, evidence and decision reports — read-only."
      />
      <PageMotion>
        <IepReportsWorkspace />
      </PageMotion>
    </div>
  );
}

"use client";

import { PageHeader } from "@/components/layout/page-header";
import { PageMotion } from "@/components/desk/motion";
import { AqcInvestigationsWorkspace } from "@/components/ops/aqc-workspaces";

export default function AqcInvestigationsPage() {
  return (
    <div>
      <PageHeader
        title="Investigations"
        description="Incident timelines from Signal → MTF → Quality → Risk → Execution."
      />
      <PageMotion>
        <AqcInvestigationsWorkspace />
      </PageMotion>
    </div>
  );
}

"use client";

import { PageHeader } from "@/components/layout/page-header";
import { PageMotion } from "@/components/desk/motion";
import { QpmReportsWorkspace } from "@/components/ops/qpm-workspaces";

export default function QpmReportsPage() {
  return (
    <div>
      <PageHeader
        title="Portfolio Reports"
        description="Allocation, ranking, exposure, diversification and executive portfolio reports."
      />
      <PageMotion>
        <QpmReportsWorkspace />
      </PageMotion>
    </div>
  );
}

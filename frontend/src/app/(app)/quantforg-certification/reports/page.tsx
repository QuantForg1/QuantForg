"use client";

import { PageHeader } from "@/components/layout/page-header";
import { PageMotion } from "@/components/desk/motion";
import { QcsReportsWorkspace } from "@/components/ops/qcs-workspaces";

export default function QcsReportsPage() {
  return (
    <div>
      <PageHeader
        title="Certification Reports"
        description="Certification, release, strategy, platform and executive readiness reports."
      />
      <PageMotion>
        <QcsReportsWorkspace />
      </PageMotion>
    </div>
  );
}

"use client";

import { PageHeader } from "@/components/layout/page-header";
import { PageMotion } from "@/components/desk/motion";
import { QcsReadinessWorkspace } from "@/components/ops/qcs-workspaces";

export default function QcsReadinessPage() {
  return (
    <div>
      <PageHeader
        title="Readiness Center"
        description="Certification levels and domain readiness — advisory only."
      />
      <PageMotion>
        <QcsReadinessWorkspace />
      </PageMotion>
    </div>
  );
}

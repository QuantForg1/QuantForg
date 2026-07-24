"use client";

import { PageHeader } from "@/components/layout/page-header";
import { PageMotion } from "@/components/desk/motion";
import { QptcmReportsWorkspace } from "@/components/ops/qptcm-workspaces";

export default function QptcmReportsPage() {
  return (
    <div>
      <PageHeader
        title="Campaign Reports"
        description="QPTCM daily, weekly, evaluation, graduation, lessons learned."
      />
      <PageMotion>
        <QptcmReportsWorkspace />
      </PageMotion>
    </div>
  );
}

"use client";

import { PageHeader } from "@/components/layout/page-header";
import { PageMotion } from "@/components/desk/motion";
import { QptcmEvidenceWorkspace } from "@/components/ops/qptcm-workspaces";

export default function QptcmEvidencePage() {
  return (
    <div>
      <PageHeader
        title="Evidence Center"
        description="QPTCM campaign evidence, incidents, and recommendations."
      />
      <PageMotion>
        <QptcmEvidenceWorkspace />
      </PageMotion>
    </div>
  );
}

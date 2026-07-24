"use client";

import { PageHeader } from "@/components/layout/page-header";
import { PageMotion } from "@/components/desk/motion";
import { QcsEvidenceWorkspace } from "@/components/ops/qcs-workspaces";

export default function QcsEvidencePage() {
  return (
    <div>
      <PageHeader
        title="Evidence Explorer"
        description="Certification evidence packs from all major enterprise subsystems."
      />
      <PageMotion>
        <QcsEvidenceWorkspace />
      </PageMotion>
    </div>
  );
}

"use client";

import { PageHeader } from "@/components/layout/page-header";
import { PageMotion } from "@/components/desk/motion";
import { QsmrEvidenceWorkspace } from "@/components/ops/qsmr-workspaces";

export default function QsmrEvidencePage() {
  return (
    <div>
      <PageHeader
        title="Evidence Viewer"
        description="Research lineage, replay, simulation, validation, risk and deployment evidence."
      />
      <PageMotion>
        <QsmrEvidenceWorkspace />
      </PageMotion>
    </div>
  );
}

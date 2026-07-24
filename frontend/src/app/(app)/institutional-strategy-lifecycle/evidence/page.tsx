"use client";

import { PageHeader } from "@/components/layout/page-header";
import { PageMotion } from "@/components/desk/motion";
import { IslmEvidenceWorkspace } from "@/components/ops/islm-workspaces";

export default function IslmEvidencePage() {
  return (
    <div>
      <PageHeader
        title="Evidence Viewer"
        description="Research, replay, simulation, CVF, risk, EQS, RES and release evidence."
      />
      <PageMotion>
        <IslmEvidenceWorkspace />
      </PageMotion>
    </div>
  );
}

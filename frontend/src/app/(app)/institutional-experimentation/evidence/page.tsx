"use client";

import { PageHeader } from "@/components/layout/page-header";
import { PageMotion } from "@/components/desk/motion";
import { IepEvidenceWorkspace } from "@/components/ops/iep-workspaces";

export default function IepEvidencePage() {
  return (
    <div>
      <PageHeader
        title="Evidence Explorer"
        description="Replay, simulation, CVF, IRAP, AI findings and statistics."
      />
      <PageMotion>
        <IepEvidenceWorkspace />
      </PageMotion>
    </div>
  );
}

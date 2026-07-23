"use client";

import { PageHeader } from "@/components/layout/page-header";
import { PageMotion } from "@/components/desk/motion";
import { AqcEvidenceWorkspace } from "@/components/ops/aqc-workspaces";

export default function AqcEvidencePage() {
  return (
    <div>
      <PageHeader
        title="Evidence Viewer"
        description="Every Copilot answer is backed by source subsystems and statistics."
      />
      <PageMotion>
        <AqcEvidenceWorkspace />
      </PageMotion>
    </div>
  );
}

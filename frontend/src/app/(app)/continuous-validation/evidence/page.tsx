"use client";

import { PageHeader } from "@/components/layout/page-header";
import { PageMotion } from "@/components/desk/motion";
import { CvfEvidenceWorkspace } from "@/components/ops/cvf-workspaces";

export default function CvfEvidencePage() {
  return (
    <div>
      <PageHeader
        title="Evidence Viewer"
        description="Every alert links to baseline, observations, research and knowledge graph."
      />
      <PageMotion>
        <CvfEvidenceWorkspace />
      </PageMotion>
    </div>
  );
}

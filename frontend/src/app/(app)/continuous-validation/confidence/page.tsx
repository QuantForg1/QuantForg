"use client";

import { PageHeader } from "@/components/layout/page-header";
import { PageMotion } from "@/components/desk/motion";
import { CvfConfidenceWorkspace } from "@/components/ops/cvf-workspaces";

export default function CvfConfidencePage() {
  return (
    <div>
      <PageHeader
        title="Confidence Explorer"
        description="Sample size, variance, stability, reliability and evidence scores."
      />
      <PageMotion>
        <CvfConfidenceWorkspace />
      </PageMotion>
    </div>
  );
}

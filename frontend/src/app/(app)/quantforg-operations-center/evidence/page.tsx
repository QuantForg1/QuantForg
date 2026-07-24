"use client";

import { PageHeader } from "@/components/layout/page-header";
import { PageMotion } from "@/components/desk/motion";
import { AocEvidenceWorkspace } from "@/components/ops/aoc-workspaces";

export default function AocEvidencePage() {
  return (
    <div>
      <PageHeader
        title="Evidence Explorer"
        description="Subsystem evidence packs feeding the operations center."
      />
      <PageMotion>
        <AocEvidenceWorkspace />
      </PageMotion>
    </div>
  );
}

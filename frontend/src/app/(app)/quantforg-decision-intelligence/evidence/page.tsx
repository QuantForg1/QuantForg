"use client";

import { PageHeader } from "@/components/layout/page-header";
import { PageMotion } from "@/components/desk/motion";
import { QdieEvidenceWorkspace } from "@/components/ops/qdie-workspaces";

export default function QdieEvidencePage() {
  return (
    <div>
      <PageHeader
        title="Evidence Graph"
        description="QDIE supporting and conflicting evidence links — read-only."
      />
      <PageMotion>
        <QdieEvidenceWorkspace />
      </PageMotion>
    </div>
  );
}

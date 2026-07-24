"use client";

import { PageHeader } from "@/components/layout/page-header";
import { PageMotion } from "@/components/desk/motion";
import { QsfEvidenceWorkspace } from "@/components/ops/qsf-workspaces";

export default function QsfEvidencePage() {
  return (
    <div>
      <PageHeader
        title="Evidence Center"
        description="QSF dossiers — strategy, research, validation, certification, paper trading."
      />
      <PageMotion>
        <QsfEvidenceWorkspace />
      </PageMotion>
    </div>
  );
}

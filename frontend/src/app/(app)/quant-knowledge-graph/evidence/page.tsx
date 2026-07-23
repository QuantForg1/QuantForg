"use client";

import { PageHeader } from "@/components/layout/page-header";
import { PageMotion } from "@/components/desk/motion";
import { QkgEvidenceWorkspace } from "@/components/ops/qkg-workspaces";

export default function QkgEvidencePage() {
  return (
    <div>
      <PageHeader
        title="Evidence Chain Viewer"
        description="Walk derived_from / confirmed_by / generated_by chains."
      />
      <PageMotion>
        <QkgEvidenceWorkspace />
      </PageMotion>
    </div>
  );
}

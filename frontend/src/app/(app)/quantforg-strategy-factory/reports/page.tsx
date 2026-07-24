"use client";

import { PageHeader } from "@/components/layout/page-header";
import { PageMotion } from "@/components/desk/motion";
import { QsfReportsWorkspace } from "@/components/ops/qsf-workspaces";

export default function QsfReportsPage() {
  return (
    <div>
      <PageHeader
        title="Factory Reports"
        description="QSF status, pipeline progress, dossier index, approval queue."
      />
      <PageMotion>
        <QsfReportsWorkspace />
      </PageMotion>
    </div>
  );
}

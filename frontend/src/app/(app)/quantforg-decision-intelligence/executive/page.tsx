"use client";

import { PageHeader } from "@/components/layout/page-header";
import { PageMotion } from "@/components/desk/motion";
import { QdieExecutiveWorkspace } from "@/components/ops/qdie-workspaces";

export default function QdieExecutivePage() {
  return (
    <div>
      <PageHeader
        title="Executive Decision Dashboard"
        description="QDIE executive brief and decision history — advisory only."
      />
      <PageMotion>
        <QdieExecutiveWorkspace />
      </PageMotion>
    </div>
  );
}

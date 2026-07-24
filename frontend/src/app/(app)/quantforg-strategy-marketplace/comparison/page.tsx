"use client";

import { PageHeader } from "@/components/layout/page-header";
import { PageMotion } from "@/components/desk/motion";
import { QsmrComparisonWorkspace } from "@/components/ops/qsmr-workspaces";

export default function QsmrComparisonPage() {
  return (
    <div>
      <PageHeader
        title="Comparison Workspace"
        description="Compare strategies by performance, risk, validation, simulation, certification and health."
      />
      <PageMotion>
        <QsmrComparisonWorkspace />
      </PageMotion>
    </div>
  );
}

"use client";

import { PageHeader } from "@/components/layout/page-header";
import { PageMotion } from "@/components/desk/motion";
import { QdieDecisionCenterWorkspace } from "@/components/ops/qdie-workspaces";

export default function QuantForgDecisionIntelligencePage() {
  return (
    <div>
      <PageHeader
        title="Decision Intelligence"
        description="QDIE — advisory recommendations. Human approval required. Never modifies production."
      />
      <PageMotion>
        <QdieDecisionCenterWorkspace />
      </PageMotion>
    </div>
  );
}

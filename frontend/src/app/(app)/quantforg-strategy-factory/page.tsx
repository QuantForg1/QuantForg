"use client";

import { PageHeader } from "@/components/layout/page-header";
import { PageMotion } from "@/components/desk/motion";
import { QsfDashboardWorkspace } from "@/components/ops/qsf-workspaces";

export default function QuantForgStrategyFactoryPage() {
  return (
    <div>
      <PageHeader
        title="Strategy Factory"
        description="QSF — idea to paper-trading readiness. Human approval required. Never deploys or trades."
      />
      <PageMotion>
        <QsfDashboardWorkspace />
      </PageMotion>
    </div>
  );
}

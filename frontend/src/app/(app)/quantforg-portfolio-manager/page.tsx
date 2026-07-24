"use client";

import { PageHeader } from "@/components/layout/page-header";
import { PageMotion } from "@/components/desk/motion";
import { QpmDashboardWorkspace } from "@/components/ops/qpm-workspaces";

export default function QuantForgPortfolioManagerPage() {
  return (
    <div>
      <PageHeader
        title="Portfolio Manager"
        description="QPM — advisory portfolio orchestration. Never allocates or rebalances automatically."
      />
      <PageMotion>
        <QpmDashboardWorkspace />
      </PageMotion>
    </div>
  );
}

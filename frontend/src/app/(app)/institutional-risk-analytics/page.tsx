"use client";

import { PageHeader } from "@/components/layout/page-header";
import { PageMotion } from "@/components/desk/motion";
import { IrapDashboardWorkspace } from "@/components/ops/irap-workspaces";

export default function InstitutionalRiskAnalyticsPage() {
  return (
    <div>
      <PageHeader
        title="Institutional Risk Analytics"
        description="Portfolio risk intelligence — VaR, drawdown, exposure, stress. Never modifies production."
      />
      <PageMotion>
        <IrapDashboardWorkspace />
      </PageMotion>
    </div>
  );
}

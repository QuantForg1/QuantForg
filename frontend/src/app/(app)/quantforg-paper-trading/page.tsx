"use client";

import { PageHeader } from "@/components/layout/page-header";
import { PageMotion } from "@/components/desk/motion";
import { QptcmDashboardWorkspace } from "@/components/ops/qptcm-workspaces";

export default function QuantForgPaperTradingPage() {
  return (
    <div>
      <PageHeader
        title="Paper Trading Campaigns"
        description="QPTCM — governed paper campaigns. Never live trades. Graduation requires human approval."
      />
      <PageMotion>
        <QptcmDashboardWorkspace />
      </PageMotion>
    </div>
  );
}

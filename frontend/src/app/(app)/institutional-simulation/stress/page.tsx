"use client";

import { PageHeader } from "@/components/layout/page-header";
import { PageMotion } from "@/components/desk/motion";
import { IseStressWorkspace } from "@/components/ops/ise-workspaces";

export default function IseStressPage() {
  return (
    <div>
      <PageHeader
        title="Stress Testing"
        description="Extreme spread, delay, volatility spike, gaps, rapid trend/reversal."
      />
      <PageMotion>
        <IseStressWorkspace />
      </PageMotion>
    </div>
  );
}

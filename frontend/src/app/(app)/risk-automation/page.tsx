"use client";

import { PageHeader } from "@/components/layout/page-header";
import { PageMotion } from "@/components/desk/motion";
import { Phase5RiskDesk } from "@/components/ops/phase5/risk-desk";

export default function RiskAutomationPage() {
  return (
    <div className="flex h-full min-h-0 flex-col">
      <PageHeader
        eyebrow="Control Center"
        title="Risk Automation"
        description="Operational risk monitoring and enforcement readout — backend gates remain authoritative."
      />
      <PageMotion className="min-h-0 flex-1 overflow-auto p-4">
        <Phase5RiskDesk />
      </PageMotion>
    </div>
  );
}

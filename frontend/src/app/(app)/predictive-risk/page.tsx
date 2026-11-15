"use client";

import { PageHeader } from "@/components/layout/page-header";
import { PageMotion } from "@/components/desk/motion";
import { Phase6RiskDesk } from "@/components/ops/phase6/risk-desk";

export default function PredictiveRiskPage() {
  return (
    <div className="flex h-full min-h-0 flex-col">
      <PageHeader
        eyebrow="Intelligence"
        title="Predictive Risk"
        description="Forward-looking risk intelligence — hard limits always win."
      />
      <PageMotion className="min-h-0 flex-1 overflow-auto p-4">
        <Phase6RiskDesk />
      </PageMotion>
    </div>
  );
}

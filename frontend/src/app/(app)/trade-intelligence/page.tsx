"use client";

import { PageHeader } from "@/components/layout/page-header";
import { PageMotion } from "@/components/desk/motion";
import { Phase7TradeIntelDesk } from "@/components/ops/phase7/trade-intel-desk";

export default function TradeIntelligencePage() {
  return (
    <div className="flex h-full min-h-0 flex-col">
      <PageHeader
        eyebrow="Autonomy"
        title="Trade Intelligence"
        description="Post-trade analysis and feedback from confirmed executions only."
      />
      <PageMotion className="min-h-0 flex-1 overflow-auto p-4">
        <Phase7TradeIntelDesk />
      </PageMotion>
    </div>
  );
}
